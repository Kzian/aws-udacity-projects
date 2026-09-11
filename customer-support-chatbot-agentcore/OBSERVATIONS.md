# Observations — Customer Support Chatbot (AgentCore Harness)

## Evaluation Summary
- Bedrock Evaluations job `support-chatbot-eval-run-1`, LLM-as-a-judge, Correctness metric, judge model Nova Pro.
- 10 test cases across all three routes (bug report, FAQ, other) plus edge cases (ambiguous, very short, prompt injection, borderline categorization).
- Aggregate correctness score: 0.95.
- 9 of 10 cases scored fully correct. One case (t8_very_short, prompt "Help") scored 0.5.

## What Changed Between Runs, and Why

### 1. Premature tool calls with fabricated fields
Early versions of the prompt allowed the model to call `create_bug_report` after only the customer's initial description, before `stepsToReproduce` or `environment` had been provided. In one case, the Lambda's own parameter validation rejected the call (missing fields) and the model recovered correctly on retry — but in a later run, the model instead responded to a validation failure by inventing plausible-sounding values for the missing fields and retrying until the call succeeded, rather than asking the customer. This was confirmed by comparing the chat transcript against the actual DynamoDB record: the stored `stepsToReproduce` value ("added an item to cart, went to checkout, and clicked Pay") did not match anything the customer had actually typed.

Fix: added an explicit rule forbidding retry-with-fabricated-values after a failed tool call, requiring the model to ask the customer instead. Also added a "VERBATIM" rule and worked examples distinguishing `description` from `stepsToReproduce` explicitly, since the model was initially treating a description of the failure ("crashes when I click Pay") as if it also satisfied the reproduction-steps field.

### 2. Leaked internal reasoning (`<thinking>` tags)
Nova's responses periodically included visible `<thinking>...</thinking>` blocks in the customer-facing output, despite an explicit prompt instruction not to. This persisted across several prompt-wording attempts. Root cause: Nova streams these tags split across multiple individual text-delta events (e.g. `"<thinking"` then `">"` as separate chunks), so `chat.py`'s original per-chunk string search could never detect the complete tag in any single chunk.

Fix: this is a code-level issue, not fully solvable through prompting alone. `chat.py` was changed to buffer each full assistant message before printing, then strip any `<thinking>...</thinking>` block with a regex applied to the complete text, rather than attempting to detect the tag mid-stream.

### 3. Incomplete environment data
The model initially accepted a bare browser name (e.g. "Chrome") as a complete `environment` value. Tightened the prompt to require both a browser and an operating system/device, with worked examples of complete vs. incomplete environments, so tickets carry more actionable detail for engineering follow-up.

### 4. Harness memory contamination
By default, AgentCore harnesses have managed memory enabled, meaning conversation state can persist across sessions. This risked one test conversation's data leaking into a later, supposedly-fresh session. Fixed by explicitly passing `memory={"disabled": {}}` in `create_harness.py`'s `create_harness()` call, and rebuilding the harness from scratch (an existing harness cannot have this setting changed in place — the memory store must not have been created in the first place).

## Known Limitation
- `t8_very_short` ("Help") was expected to prompt a clarifying question per the prompt's own ambiguity-handling rule, but the model instead classified it as OTHER and gave the standard human hand-off. This is a minor, defensible edge case — the model's behavior is not incorrect, and a redirect to human support for an unclarified "Help" is a reasonable outcome, but the intended clarifying-question behavior did not trigger reliably for extremely short inputs.

## Per-Record Score Analysis
9 of 10 test cases scored 1.0. The one exception, `t8_very_short` ("Help"), scored 0.5 — the judge model found the response partially, not fully, aligned with the reference. My prompt's own ambiguity-handling rule says a short or vague message should get one clarifying question; the model instead classified the single word "Help" as OTHER and issued the standard hand-off. Given more iteration time, I would tighten the ambiguity rule to explicitly mention very short/single-word messages as a trigger for a clarifying question, specifically calling out one- or two-word inputs, and re-run the evaluation to see if that raises this case to a full score without regressing the nine that already pass.
