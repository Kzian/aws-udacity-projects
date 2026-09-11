# Customer Support Chatbot — Amazon Bedrock AgentCore

A customer support chatbot for a fictional online shop, built on the **Amazon Bedrock AgentCore managed harness**. All routing, information-gathering, and grounding behavior lives in a single system prompt — there's no separate classifier or condition-node graph. The harness supplies the agent loop (model calls, stateful sessions, tool execution); the prompt supplies the behavior.

> **Context:** Bedrock Agents Classic closed to new customers on July 30, 2026. This project uses its successor, the AgentCore managed harness.

## What it does

The chatbot classifies every incoming message into exactly one of three categories and responds accordingly:

| Category | Behavior |
|---|---|
| **Bug report** | Collects `description`, `stepsToReproduce`, and `environment` one field at a time across the conversation, then files a ticket via the `create_bug_report` tool (a Lambda function exposed through an AgentCore Gateway) and relays the ticket ID |
| **Platform question** | Answers strictly from an FAQ document embedded in the prompt (orders, shipping, returns, payments, etc.) — hands off to human support if the FAQ doesn't cover the question |
| **Other** | Politely redirects to the human support line |

## Architecture

    Customer message
          |
          v
    system_prompt.txt (routing + all three behaviors)
          |
          v
    AgentCore managed harness (model: Nova Pro, memory disabled)
          |
          +-- Bug report --> AgentCore Gateway --> Lambda --> DynamoDB (ticket storage)
          +-- Platform question --> answered from embedded FAQ
          +-- Other --> redirect message

**Stack:** Amazon Bedrock AgentCore (managed harness + Gateway), AWS Lambda, Amazon DynamoDB, Amazon Bedrock Evaluations (LLM-as-a-judge).

## Files

| File | Purpose |
|---|---|
| `system_prompt.txt` | The core deliverable — defines all routing and behavior |
| `chat.py` | Terminal client for multi-turn testing against the harness |
| `create_harness.py` | Creates/updates the AgentCore harness from `system_prompt.txt` |
| `harness-tests.json` | Automated test suite covering all three routes plus edge cases |
| `output_eval_dataset.jsonl` | Generated dataset (prompt, reference, actual response) used for evaluation |
| `bug-report-transcript.txt` | Sample multi-turn bug report conversation, ending in a real ticket ID |
| `faq-and-other-transcript.txt` | Sample FAQ (covered/uncovered) and out-of-scope conversation |
| `OBSERVATIONS.md` | Detailed write-up of debugging history, prompt iterations, and evaluation analysis |

## Evaluation results

Tested with 10 cases across all three routes plus edge cases (ambiguous messages, very short input, prompt injection, borderline categorization), scored with **Bedrock Evaluations** using **LLM-as-a-judge** (Builtin.Correctness metric, Nova Pro as judge):

- **Aggregate correctness: 0.95**
- 9 of 10 cases scored 1.0
- 1 case ("Help") scored 0.5 — a known limitation in ambiguity handling for single-word inputs (see OBSERVATIONS.md for the full analysis and proposed fix)

## Notable debugging findings

Documented in full in OBSERVATIONS.md:
- **Fabricated tool-call fields**: the model would sometimes invent plausible-sounding `stepsToReproduce`/`environment` values after a failed tool call rather than asking the customer — fixed with explicit anti-fabrication rules and worked examples distinguishing each required field.
- **Leaked chain-of-thought**: Nova's `<thinking>` reasoning periodically leaked into customer-facing responses. The tag itself streams split across multiple events, so per-chunk detection couldn't catch it — fixed by buffering full responses and stripping the tag with a regex after streaming completes.
- **Harness memory contamination**: AgentCore harnesses default to memory *enabled*, risking cross-session data leakage. Fixed by explicitly disabling memory at harness creation.

## Note on scope

This implementation covers the AgentCore harness path only (bug report, FAQ, and other-request handling, plus testing/evaluation), per the project's current instructions. An earlier, now-superseded rubric version also referenced a Bedrock Flow (classifier + condition-node) implementation — that architecture was not built here, as the final project rubric confirmed the AgentCore-only implementation satisfies all requirements.
