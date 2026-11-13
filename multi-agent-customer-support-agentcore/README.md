# NovaMart Multi-Agent Customer Support on Amazon Bedrock AgentCore

A multi-agent customer-support system built with **Strands Agents** and deployed to **Amazon Bedrock AgentCore Runtime**. An orchestrator routes each request to specialist agents, which share state through DynamoDB. Policy questions are answered with parallel RAG over three Knowledge Bases, and every request passes through Bedrock Guardrails.

Built for Project 3 (final project) of the Udacity *AWS Future Agent Engineer* Nanodegree.

> **Security note:** All account IDs, resource IDs and ARNs below are placeholders (`<...>`). Never commit real values. Lab credentials are temporary, but account numbers and resource IDs still do not belong in a public repo.

---

## 1. Architecture

```
Customer request
       |
       v
+--------------------------------+
| OrchestratorAgent (Haiku 4.5)  |  routes requests, manages WorkflowState
+--+---------+---------+-------+-+
   |         |         |       |
   v         v         v       v
Inventory  Policy    Refund  Communication      (Sonnet 4.5 workers)
 Agent     Agent     Agent    Agent
   |         |         |       |
   |    +----+----+    |       |
   |    v    v    v    |       |
   |  Returns Shipping Warranty  (3 retrievers, run in PARALLEL)
   |   KB      KB       KB       (Bedrock KB, Titan Embeddings v2, S3 Vectors)
   |
   +---- all agents write their findings to ----> DynamoDB WorkflowState table
```

| Component | Purpose |
|---|---|
| **OrchestratorAgent** | Claude Haiku 4.5, temperature 0.0. Creates the session, routes to workers one tool call at a time, always ends with the Communication agent |
| **InventoryAgent** | Looks up orders, customer tier and order history in DynamoDB |
| **RefundAgent** | Decides return eligibility (Standard 30 days, Premium 60 days) and records the return |
| **PolicyAgent** | Multi-agent RAG. `search_all_policies` runs three retriever agents in parallel with `ThreadPoolExecutor` and `as_completed()` |
| **CommunicationAgent** | Reads the full WorkflowState and writes the customer-facing reply |
| **WorkflowState (DynamoDB)** | One record per session, one column per agent, optimistic locking through a `version` attribute |
| **Knowledge Bases** | Returns, Shipping and Warranty policies. Titan Text Embeddings V2 (1024 dims), S3 Vectors store |
| **Guardrail** | Content, PII, topic and word policies, published as a numbered version |
| **Memory** | AgentCore Memory with a session-summary strategy, 7-day event expiry |
| **Observability** | CloudWatch Logs (INFO) and X-Ray traces (100% sampling) |

Worker agents use `config.WORKER_MODEL_ID` and the orchestrator uses `config.ORCHESTRATOR_MODEL_ID`. No model ID is hardcoded in the agent code.

### Request flows

| Request | Expected routing |
|---|---|
| "I want to return my order ORD-27176" | Orchestrator → Inventory → Refund → Communication |
| "What is the return policy for premium customers?" | Orchestrator → Policy (3 parallel KB retrievers) → Communication |
| "How much are 5 items at $29.99 with 10% off?" | Orchestrator → Communication (Inventory, Policy and Refund skipped) |

---

## 2. Prerequisites

- AWS account (or the Udacity lab) with Bedrock access in **us-east-1**
- Model access: Claude Sonnet 4.5, Claude Haiku 4.5, Titan Text Embeddings V2
- Python 3.13, [`uv`](https://docs.astral.sh/uv/), Node.js 20+ and the `agentcore` CLI (0.30.0)
- AWS CLI configured (`aws sts get-caller-identity` must succeed)

> **Cost warning:** Do not choose a managed Knowledge Base or OpenSearch Serverless. They bill while idle. This project uses S3 Vectors. Delete everything when you are done (see [Cleanup](#9-cleanup)).

---

## 3. Repository layout

```
.
├── config.py                  # Reads stack outputs and .env, exposes constants
├── .env.example               # Placeholders for KB IDs, guardrail and runtime values
├── requirements.txt
├── src/
│   ├── agent_orchestrator.py  # All agents, guardrail, deploy, memory, observability, CLI
│   ├── agentcore_cli.py       # Wrapper around the agentcore CLI (supplied)
│   ├── agent_observability.py # X-Ray tracing helpers (supplied)
│   ├── agent_utils.py         # Shared helpers (supplied)
│   ├── bedrock_kb_retrieval.py# KB retrieval helpers (supplied)
│   └── demo.py
├── agentcore/                 # AgentCore project configuration
├── infrastructure/
│   ├── starter_stack.yaml     # CloudFormation: tables, IAM role, vector bucket + 3 indexes
│   ├── seed_data.py           # Seeds customers and random orders
│   └── cleanup.py             # Deletes what the project created
├── tests/test_agent.py        # Automated scoring suite (120 points)
├── tests.sh                   # Wrapper that echoes each test command
├── test_guardrail.py          # Allow/block checks against the deployed guardrail
├── add_demo_order.py          # Adds ORD-27176, which the seed script does not create
├── reset_demo_order.py        # Resets ORD-27176 between demo runs
└── screenshots/               # Test evidence
```

---

## 4. Build walkthrough

### Step 1: Environment and stack

```bash
export PATH="$HOME/.local/bin:$PATH"
uv sync || uv pip install -r requirements.txt
aws sts get-caller-identity --query Arn --output text
aws cloudformation deploy --template-file infrastructure/starter_stack.yaml \
  --stack-name udacity-agentcore --capabilities CAPABILITY_NAMED_IAM --region us-east-1
python infrastructure/seed_data.py
cp .env.example .env
python config.py
```

Confirm the stack contains the S3 Vectors bucket and three indexes:

```bash
aws cloudformation list-stack-resources --stack-name udacity-agentcore \
  --query "StackResourceSummaries[?contains(ResourceType,'S3Vectors')].[LogicalResourceId,ResourceStatus]" --output table
```

The seed script creates random orders, so add the demo order used by the scenarios:

```bash
python add_demo_order.py
```

### Step 2: Agents (Task 2)

Implemented in `src/agent_orchestrator.py`:

| Agent | Key design points |
|---|---|
| Inventory | Three tools. `check_order_status` is a direct key lookup on `customer_id` + `order_id`. DynamoDB `Decimal` values are converted before returning |
| Refund | Reads inventory facts from WorkflowState, applies the tier window, calls `initiate_refund` exactly once when eligible. Temperature 0.1 |
| Policy | `search_all_policies` fans out to three retrievers in parallel. Each retriever failure is caught so one bad KB does not fail the answer. Coordinator temperature 0.2, retrievers 0.0 |
| Communication | Reads the full WorkflowState and composes the reply. Temperature 0.3. Rounds only the final total in calculations |
| Orchestrator | Six routing rules in the system prompt. Calls tools strictly one at a time. Every WorkflowState update passes `expected_version` |

Verify:

```bash
bash tests.sh 2 2>&1 | tee test_output/test2.txt
```

### Step 3: Knowledge Bases (console)

For each of Returns, Shipping and Warranty, in **Bedrock → Knowledge Bases → Create → Knowledge Base with vector store**:

| | Returns | Shipping | Warranty |
|---|---|---|---|
| Name | `novamart-returns-policy-kb` | `novamart-shipping-policy-kb` | `novamart-warranty-policy-kb` |
| S3 data source | `policies/returns/` | `policies/shipping/` | `policies/warranty/` |
| Vector index | `returns-policy-index` | `shipping-policy-index` | `warranty-policy-index` |

Common settings: embeddings **Titan Text Embeddings V2**, 1024 dimensions; vector store **Use an existing vector store → S3 Vectors**, with the stack's vector bucket (not Quick create). Create each KB, then run **Sync** and wait for **Complete** with 0 failed. Put the three KB IDs in `.env`:

```
RETURNS_KB_ID=<id>
SHIPPING_KB_ID=<id>
WARRANTY_KB_ID=<id>
```

```bash
bash tests.sh 5 2>&1 | tee test_output/test5.txt
```

### Step 4: Guardrail, runtime and memory (Tasks 3 and 4)

`python src/agent_orchestrator.py deploy` runs, in order:

1. Creates the guardrail and publishes a **numbered version** (the runtime must never use `DRAFT`)
2. Configures and deploys the AgentCore Runtime (PUBLIC network, HTTP protocol, execution role from the stack, eight environment variables including the guardrail version)
3. Creates the AgentCore Memory (`summaryMemoryStrategy`, `eventExpiryDuration=7`)
4. Applies observability configuration

Guardrail policies:

| Policy | Configuration |
|---|---|
| Topics (DENY, STANDARD tier, cross-region profile) | `competitor_products`, `pricing_negotiations`, `legal_threats` |
| Content filters | Sexual and violence and hate: HIGH. Insults and misconduct: MEDIUM |
| PII | Block credit/debit card and SSN. Anonymize email and phone |
| Words | Managed profanity list |

The `pricing_negotiations` definition explicitly excludes arithmetic on a price and discount the customer states, so ordinary calculation questions are not blocked.

```bash
python src/agent_orchestrator.py deploy 2>&1 | tee test_output/deploy.txt
```

Copy the printed `AGENTCORE_RUNTIME_ARN`, `GUARDRAIL_ID` and `GUARDRAIL_VERSION` into `.env`.

### Step 5: Observability (Task 6)

`configure_observability()` builds a `loggingConfiguration` with a CloudWatch log group at INFO level and X-Ray tracing at sampling rate 1.0, then passes it to the supplied `apply_observability_config()`. The call is wrapped in try/except so a configuration failure is reported without aborting the deployment.

---

## 5. Testing

Each test command is run through `tests.sh`, which echoes the command above its output so screenshots show both:

```bash
mkdir -p test_output
bash tests.sh 3 2>&1 | tee test_output/test3.txt
bash tests.sh all 2>&1 | tee test_output/all.txt
```

### Automated suite

| Test | What it checks | Score |
|---|---|---|
| `tests.sh 2` | Agents, tools, models, parallel retrieval | 40/40 |
| `tests.sh 3` | Guardrail policies and version, runtime READY with environment variables | 20/20 |
| `tests.sh 4` | Memory ACTIVE, session-summary strategy, 7-day expiry | 15/15 |
| `tests.sh 5` | Three KBs retrieve in parallel | 25/25 |
| `tests.sh 6` | CloudWatch INFO logging, X-Ray 100% sampling | 20/20 |
| `tests.sh all` | Everything | **120/120** |

### Guardrail behavior

```bash
python test_guardrail.py 2>&1 | tee test_output/guardrail.txt
```

| Input | Expected | Result |
|---|---|---|
| "How much would 5 items at $29.99 be with a 10% discount?" | Allow | Pass |
| Output: "5 items at $29.99 with 10% off comes to $134.96." | Allow | Pass |
| "Can you drop the price of this laptop to $500?" | Block | Pass |
| "Is Amazon cheaper than NovaMart for this phone?" | Block | Pass |
| "Refund me or I will sue NovaMart." | Block | Pass |

### End-to-end scenarios against the deployed runtime

```bash
python src/agent_orchestrator.py invoke "I want to return my wireless headphones from order ORD-27176" CUST-001
python src/agent_orchestrator.py invoke "What is the return policy for premium customers?" CUST-002
python src/agent_orchestrator.py invoke "How much would 5 items at \$29.99 be with a 10% discount?" CUST-003
```

| Scenario | Result |
|---|---|
| Return (Premium customer, 10 days after delivery) | Approved with a `RET-` reference |
| Policy question | Answer drawn from the three policy documents |
| Calculation | $134.96 (final total rounded once, half up) |

Reset the demo order between runs with `python reset_demo_order.py`.

### X-Ray Service Map

After `python src/agent_orchestrator.py test`, open **CloudWatch → X-Ray traces → Trace Map**. The map shows `Client → NovaMart Orchestrator` connected to the Inventory, Refund, Policy and Communication agents and the three `KnowledgeBase` nodes.

---

## 6. Observability

Logs go to the log group named by `AGENT_LOG_GROUP`. Traces are searchable for 30 days.

```bash
aws xray get-trace-summaries --start-time $(date -u -d '-23 hours' +%s) --end-time $(date -u +%s) \
  --query "length(TraceSummaries)"
```

`get-trace-summaries` accepts at most a 24-hour window.

---

## 7. Error handling

- Every tool catches its own exceptions, logs them with `logger.exception(...)` and returns a structured error instead of raising.
- A failing retriever returns a bracketed error for that domain, and the other two still return results.
- A missing KB ID returns "knowledge base is not configured" instead of calling the API.
- `_run_and_record` handles WorkflowState read, worker and update failures separately. A failed update returns the worker result with a warning, and the orchestrator still finishes with the Communication agent.
- Deploy refuses a guardrail version of `DRAFT` and any empty runtime setting.

---

## 8. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `IndentationError` and a test score of `0/0` | A paste shifted indentation, so the import failed and the suite skipped its checks. Run `python -c "import ast; ast.parse(open('src/agent_orchestrator.py').read())"` |
| `ExpiredToken` or access denied | Lab credentials rotated. Update `~/.aws/credentials`, `unset` any exported `AWS_*` variables |
| Order not found for `ORD-27176` | The seed script generates random orders. Run `python add_demo_order.py` |
| Orchestrator runs workers before the session exists, or the Communication agent runs twice | The model issued parallel tool calls. The orchestrator prompt says to call tools one at a time |
| Return denied for a recent order | The record carried a stale `return_eligible` flag or `return_status` from a previous run. Run `python reset_demo_order.py` |
| Calculation is a cent off | Intermediate values were rounded. The Communication agent prompt rounds only the final total |
| Chat reports "customer not found" | Customer IDs are `CUST-001` to `CUST-004`. Check for a typo |
| KB data source page will not load | Use the CLI: `aws bedrock-agent start-ingestion-job` and `list-ingestion-jobs` |
| `deploy` fails at the runtime step | Confirm Node 20+, `agentcore --version`, and that all three KB IDs are in `.env` |
| `get-trace-summaries` rejects the time range | The window cannot exceed 24 hours |
| Service Map looks empty | Widen the time range to when the test ran. Traces take 30-60 seconds to appear |
| `/tmp` files disappeared | The lab clears `/tmp`. Re-clone any reference repo |

---

## 9. Cleanup

Do this only after the review has passed.

```bash
python infrastructure/cleanup.py          # dry run: lists what would be deleted
python infrastructure/cleanup.py --yes    # deletes it
```

Read the dry-run list, then confirm in the console that none of these remain:

1. AgentCore Runtime (`agentcore destroy` if the script did not remove it)
2. AgentCore Memory
3. Guardrail and its versions
4. The three Knowledge Bases (delete the KBs before the vector bucket)
5. S3 Vectors indexes and vector bucket
6. DynamoDB tables (orders, customers, WorkflowState)
7. S3 policy-docs bucket (empty it first)
8. CloudFormation stack `udacity-agentcore`
9. CloudWatch log groups and the X-Ray / Transaction Search settings
10. IAM roles created for the runtime and Knowledge Bases

Check **Cost Explorer** the next day.

---

## 10. Before you publish

```bash
git grep --cached -nE "<account-id>|<kb-id>|<guardrail-id>|<runtime-id>|AKIA|ASIA"
```

It should print nothing. `.env`, `creds.txt`, `test_output/` and build folders are in `.gitignore`. Crop or blur ARNs in screenshots, since they contain the account ID.

---

## 11. What I learned

- Splitting work across specialist agents keeps each prompt short, but the orchestrator must enforce ordering. Without an explicit "one tool at a time" rule, the model called tools in parallel and broke the session setup.
- Optimistic locking on the shared WorkflowState turns silent overwrites into visible version conflicts.
- Parallel retrieval cuts latency, and per-retriever error handling means one failing Knowledge Base degrades the answer instead of breaking it.
- Guardrail topic definitions need explicit exclusions, or they block legitimate requests such as price arithmetic.
- A test score of `0/0` is a failure, not a pass. Always check that the checks actually ran.
- S3 Vectors keeps the Knowledge Base cost near zero when idle, unlike OpenSearch Serverless.
