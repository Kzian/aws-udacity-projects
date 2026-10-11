# AWS Udacity Projects

A collection of projects completed as part of the **AWS AI & ML Scholars** program (Future AWS Agent Engineer track), delivered via Udacity in partnership with AWS.

Each project lives in its own subfolder, with its own README, code, prompts, and evaluation evidence.

---

## Projects

# A

### [customer-support-chatbot-agentcore](./customer-support-chatbot-agentcore)
A customer support chatbot built on the **Amazon Bedrock AgentCore managed harness**, handling three request types through a single system prompt:
- **Bug reports** — collects description, steps to reproduce, and environment across a multi-turn conversation, then files a ticket via a Lambda tool through an AgentCore Gateway, persisted to DynamoDB.
- **Platform questions** — answered strictly from an embedded FAQ document, with no fabricated details.
- **Other requests** — politely redirected to a human support line.

Tested with an automated suite across all three routes plus edge cases (ambiguous messages, prompt injection attempts), evaluated using **Bedrock Evaluations** with LLM-as-a-judge (Correctness metric) — achieved a **0.95** aggregate score.

Includes real debugging history: fixing premature/fabricated tool calls, a Nova chain-of-thought leak into customer-facing output, and AgentCore harness memory contamination between sessions. Full write-up in the project's `OBSERVATIONS.md`.

---

# B

### [AI Customer Support Agent (Amazon Bedrock AgentCore)](./ai-support-agent-agentcore)

An e-commerce support agent built on AgentCore. It handles order tracking,
refunds, product questions, loyalty discounts and web lookups, and remembers
customers across sessions.

## Capabilities
| Capability | Implementation |
|---|---|
| Runtime | `BedrockAgentCoreApp` with an async `@app.entrypoint` |
| Order and refund tools | AgentCore Gateway (MCP): an API Gateway REST API target and a Lambda target |
| Knowledge Base (RAG) | `search_knowledge_base`, using the Bedrock Retrieve API |
| Long-term memory | `MemoryHook` (semantic + user-preference strategies) |
| Loyalty discount | Code Interpreter sandbox with a tier-only fallback |
| Browser | `AgentCoreBrowser` |

## Files
- `main.py`: the agent
- `REFLECTION.md`: design decision, challenge, production considerations
- `screenshots/`: the six test runs

## Configuration
Set `GATEWAY_URL`, `KB_ID`, `MEMORY_ID` and `REGION` in `main.py`.
The committed file contains placeholders for the first three.

## Test results
| Test | Result |
|---|---|
| 1 Order tracking | Pass |
| 2 Refund | Pass |
| 3 Knowledge Base | Pass |
| 4 Cross-session memory | Pass |
| 5 Loyalty discount | Pass |
| 6 Browser | Pass |

## Notes
- The Gateway uses the NONE authorizer. This is for the lab only; production
  should use JWT or IAM authentication.
- All AWS resources were deleted after completion.

*More projects will be added here as the program progresses.*
