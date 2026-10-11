# AI Support Agent on Amazon Bedrock AgentCore

A customer-support agent built on **Amazon Bedrock AgentCore**. It tracks orders and processes refunds through an MCP Gateway, answers policy questions with RAG, remembers customers across sessions, calculates loyalty discounts in a sandbox, and browses the web.

Built for Project 2 of the Udacity *AWS Future Agent Engineer* Nanodegree.

> **Security note:** All account IDs, resource IDs and URLs below are placeholders (`<...>`). Never commit real values. Lab credentials are temporary, but resource IDs and account numbers still do not belong in a public repo.

---

## 1. Architecture

```
                     agentcore invoke
                           |
                           v
              +---------------------------+
              |  AgentCore Runtime        |   main.py (BedrockAgentCoreApp)
              |  Strands Agent            |   Model: Amazon Nova 2 Lite
              +------+------+------+------+
                     |      |      |
     +---------------+      |      +------------------+
     v                      v                         v
+-----------+      +----------------+       +--------------------+
| AgentCore |      | Knowledge Base |       | Code Interpreter   |
| Gateway   |      | (RAG, Retrieve)|       | loyalty discount   |
| (MCP)     |      +----------------+       +--------------------+
+-----+-----+                  +----------------+   +-----------------+
      |                        | AgentCore      |   | AgentCoreBrowser|
 +----+-----+                  | Memory         |   | web lookups     |
 v          v                  | (MemoryHook)   |   +-----------------+
order-     refund-             +----------------+
tracker    processor
(Lambda)   (Lambda)
   ^          ^
   +-- REST API (API Gateway) --+
```

| Component | Purpose |
|---|---|
| **Runtime** | Hosts the agent (`@app.entrypoint`) as a managed endpoint |
| **Gateway (MCP)** | Exposes the order and refund APIs as tools (`order-tracker___get_order`, and the refund tool) |
| **Knowledge Base** | Retrieves return, shipping and loyalty policy documents |
| **Memory** | Long-term facts and preferences per customer, namespaced `cs_agent/{actorId}/facts` and `/preferences` |
| **Code Interpreter** | Runs the loyalty-discount calculation in an isolated sandbox |
| **Browser** | Fetches live web pages |

---

## 2. Prerequisites

- AWS account with Bedrock AgentCore access in **us-east-1**
- Python 3.13 and [`uv`](https://docs.astral.sh/uv/)
- AWS CLI configured (`aws sts get-caller-identity` must succeed)
- Model access to `global.amazon.nova-2-lite-v1:0`

> **Cost warning:** A managed Knowledge Base uses OpenSearch Serverless, which bills continuously. Delete it as soon as you finish (see [Cleanup](#9-cleanup)).

---

## 3. Repository layout

```
.
├── main.py                  # Agent: tools, memory hook, gateway handling, entrypoint
├── setup_permissions.py     # Grants the runtime role access to KB, Memory, etc.
├── lambda/
│   ├── order_tracker.py     # lambda_handler: routes on event["resource"]
│   └── refund_processor.py  # lambda_handler: processes refunds
├── tests.sh                 # Wrapper that echoes each agentcore invoke command
├── screenshots/             # Test evidence
└── reflection.md
```

---

## 4. Build walkthrough

### Step 1: Environment

```bash
cd ~/Project_starter
pip install uv
export PATH="$HOME/.local/bin:$PATH"
uv sync
aws sts get-caller-identity
```

### Step 2: Lambda functions and REST API

1. In **Lambda**, create `order-tracker` and `refund-processor` from the provided `order_tracker.py` and `refund_processor.py` (handler `lambda_handler`).
2. In **API Gateway**, create a REST API with resources for orders and refunds, integrate each with its Lambda (proxy integration), and deploy to a stage.
3. Test the endpoint and confirm you get HTTP 200 with order data.

### Step 3: AgentCore Gateway

1. Create a Gateway with **inbound auth: None** (lab setting; use a real authorizer in production).
2. Add one target per API. **Target names allow only letters, digits and hyphens**, so use `order-tracker` and `refund-processor`. Underscores are rejected.
3. Tools then appear as `<target>___<tool>`, for example `order-tracker___get_order`.
4. Copy the Gateway MCP URL. It goes in `GATEWAY_URL` in `main.py`.

> If target creation fails with *"Gateway execution role lacks permission to invoke Lambda"*, wait a minute and retry. It is usually IAM propagation delay.

Verify with a `tools/list` call to the Gateway. You should see both targets' tools.

### Step 4: Knowledge Base

1. Create a managed Knowledge Base with an S3 data source holding the policy documents, then sync.
2. Use the **Test** tab to confirm a question like "What is the return policy?" returns chunks.
3. Copy the 10-character Knowledge Base ID into `KB_ID`.

### Step 5: Memory

1. Create an AgentCore Memory with two strategies: **facts** (semantic) and **preferences** (user preference).
2. Copy the memory ID (format `Name-xxxxxxxxxx`) into `MEMORY_ID`.

### Step 6: Configure `main.py`

```python
REGION      = "us-east-1"
GATEWAY_URL = "<gateway-mcp-url>"
KB_ID       = "<kb-id>"
MEMORY_ID   = "<memory-id>"
```

What the code does:

| Section | Behavior |
|---|---|
| `MemoryHook` | On each user message, retrieves facts and preferences and prepends them as `Customer Context:`. After each invocation it saves the **original** user query (not the injected context). |
| `search_knowledge_base` | Calls the Bedrock Retrieve API and joins chunks with `---` |
| `calculate_loyalty_discount` | Runs code in Code Interpreter: 100 points = $1, 500-point minimum, 50% cap |
| Gateway loading | Paginates `list_tools_sync`, logs the tool count, and handles failure (see [section 7](#7-gateway-error-handling)) |
| `invoke()` | Async entrypoint receiving `prompt`, `customer_id` and `session_id` |

### Step 7: Configure and deploy

```bash
uv run agentcore configure -e main.py
```

Answer the prompts: deployment type `direct_code_deploy`, runtime `PYTHON_3_13`, and press Enter to auto-create the S3 bucket.

Grant permissions. This script reads `KB_ID`, `MEMORY_ID` and `REGION` from `main.py`:

```bash
uv run python setup_permissions.py
```

Deploy:

```bash
uv run agentcore deploy
```

---

## 5. Testing

Each test runs `agentcore invoke` with a JSON payload. `tests.sh` wraps the command so the exact invocation is echoed above each response, which makes the evidence easy to screenshot.

```bash
mkdir -p test_output
bash tests.sh 1 2>&1 | tee test_output/test1.txt
```

You can also invoke directly:

```bash
uv run agentcore invoke '{"prompt": "Can you track order ORD-001?", "customer_id": "CUST-123", "session_id": "t1"}'
```

| # | Capability | What to verify |
|---|---|---|
| 1 | **Gateway: order tracking** | Real order data (ORD-001: Shipped, UPS, tracking number, delivery date) |
| 2 | **Gateway: refund** | A second, distinct Gateway tool is called |
| 3 | **Knowledge Base (RAG)** | Answer reflects the policy documents |
| 4a | **Memory: store** | Tell the agent your name and a preference in session A |
| 4b | **Memory: recall** | In a new session (B) with the same `customer_id`, the agent recalls the name and preference |
| 5 | **Code Interpreter** | Loyalty discount: $99.00 final total, $51 saved, 250 points remaining |
| 6 | **Browser** | Returns the page title of a live site (udacity.com) |

**Why memory persists across sessions:** memory is keyed by `customer_id` (the actor), not the session. Reusing `CUST-123` retrieves earlier facts. Use a fresh ID if you want a clean slate.

---

## 6. Observability

```bash
aws logs tail /aws/bedrock-agentcore/runtimes/<runtime-name>-DEFAULT \
  --log-stream-name-prefix "<yyyy/mm/dd>/[runtime-logs" --since 1h --follow
```

Filter for the agent's own logger and trim long lines:

```bash
aws logs tail /aws/bedrock-agentcore/runtimes/<runtime-name>-DEFAULT \
  --since 15m --filter-pattern '"CSAI_Agent"' | cut -c1-220 | head -n 15
```

---

## 7. Gateway error handling

If the Gateway is unreachable, the agent does **not** crash and does **not** invent data.

- Connection, timeout and generic errors are caught separately and logged with `logger.exception(...)`.
- On success it logs `Gateway connected successfully. Loaded N tools.`
- On failure the agent keeps its other tools (knowledge base, loyalty discount, browser, memory). A system note tells it to say order and refund services are temporarily unavailable and that no action was taken.

### Failure test

1. Temporarily set `GATEWAY_URL` to a dummy value:
   ```python
   GATEWAY_URL = "https://dummy-gateway.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
   ```
2. Redeploy and invoke:
   ```bash
   uv run agentcore deploy
   bash tests.sh 1
   ```
3. Expected response:
   > Sorry, order tracking and refund services are temporarily unavailable. Please try again in a few minutes or contact support for assistance.
4. Expected log line: `ERROR:CSAI_Agent:Gateway tool loading failed: ...`
5. **Restore the real URL, redeploy, and re-run Test 1** to confirm recovery.

---

## 8. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `uv: command not found` | `export PATH="$HOME/.local/bin:$PATH"` and `cd` into the project directory |
| Gateway target name rejected | Use hyphens, not underscores |
| "Gateway execution role lacks permission to invoke Lambda" | IAM propagation delay; retry after a minute, or add an inline policy allowing `lambda:InvokeFunction` |
| `setup_permissions.py` can't find IDs | `KB_ID` must be 10 alphanumeric characters and `MEMORY_ID` must match `Name-xxxxxxxxxx` in `main.py` |
| Agent returns "services unavailable" | Check `GATEWAY_URL`, then the logs for `Gateway tool loading failed` |
| Console banners about `uxc:GetAccountCustomizations` or `acm:ListCertificates` | Harmless lab permission notices |

---

## 9. Cleanup

Delete resources in this order to avoid ongoing charges:

```bash
uv run agentcore destroy
```

Then in the console: **Gateway**, **Memory**, **Knowledge Base**, **OpenSearch Serverless collection** (if one remains), **S3 bucket**, **REST API**, **Lambda functions**. Check **Cost Explorer** afterwards.

---

## 10. Before you publish

```bash
git grep --cached -nE "<account-id>|<api-id>|<gateway-id>|AKIA|ASIA"
```

It should print nothing. Crop or blur ARNs in screenshots, since they contain the account ID.

---

## 11. What I learned

- Gateway turns existing REST APIs into MCP tools without changing the Lambdas.
- Memory is scoped by actor, so it persists across sessions by design.
- Failure handling matters: a missing dependency should degrade the agent, not break it or make it fabricate answers.
- Managed vector stores carry real cost, so cleanup is part of the build.
