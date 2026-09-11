# AWS Udacity Projects

A collection of projects completed as part of the **AWS AI & ML Scholars** program (Future AWS Agent Engineer track), delivered via Udacity in partnership with AWS.

Each project lives in its own subfolder, with its own README, code, prompts, and evaluation evidence.

---

## Projects

### [customer-support-chatbot-agentcore](./customer-support-chatbot-agentcore)
A customer support chatbot built on the **Amazon Bedrock AgentCore managed harness**, handling three request types through a single system prompt:
- **Bug reports** — collects description, steps to reproduce, and environment across a multi-turn conversation, then files a ticket via a Lambda tool through an AgentCore Gateway, persisted to DynamoDB.
- **Platform questions** — answered strictly from an embedded FAQ document, with no fabricated details.
- **Other requests** — politely redirected to a human support line.

Tested with an automated suite across all three routes plus edge cases (ambiguous messages, prompt injection attempts), evaluated using **Bedrock Evaluations** with LLM-as-a-judge (Correctness metric) — achieved a **0.95** aggregate score.

Includes real debugging history: fixing premature/fabricated tool calls, a Nova chain-of-thought leak into customer-facing output, and AgentCore harness memory contamination between sessions. Full write-up in the project's `OBSERVATIONS.md`.

---

*More projects will be added here as the program progresses.*
