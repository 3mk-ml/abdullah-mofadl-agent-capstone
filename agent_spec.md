# DocPilot AI - Agent Specification (Week 5 / Track B)

**Domain:** Document processing. **Architecture:** One LLM agent, not multi-agent.

**Goal (one sentence):** Given uploaded PDF, TXT, or Markdown documents, the agent finds evidence, extracts deadlines, answers document questions with page references, optionally saves an approved report, and records its decisions and cost.

## Allowed tools (exactly eight)

| Tool | Source | Permission | Purpose |
|---|---|---|---|
| `list_documents` | Custom MCP | auto-read | Discover uploaded documents and page counts |
| `search_documents` | Custom MCP | auto-read | Retrieve short relevant excerpts with page references |
| `read_document` | Custom MCP | auto-read | Examine the text of a specific page |
| `find_dates` | Custom MCP | auto-read | Extract candidate date strings, not infer obligations |
| `recall_memory` | Local SQLite | auto-read | Retrieve a user-approved preference |
| `save_memory` | Local SQLite | ask-on-write | Remember an approved preference across restarts |
| `save_report` | Local SQLite | ask-on-write | Store a report only after human approval |
| `final_answer` | Agent control | auto | Terminate with answer and source references |

## Limits and termination

- **Hard maximum:** `max_turns = 8` model calls; third identical tool request ends with `repetition_limit`.
- **Budget:** `$0.03 USD per task` default, with conservative next-call reservation; abort with `budget_limit` if a call cannot fit. Max model output is 900 tokens per call.
- **Soft success:** `final_answer(answer, citations)` is required for a completed task. Direct assistant prose is insufficient.
- **Failure:** invalid provider response, MCP transport failure after unrecoverable attempts, repeated calls, max turns or cost stop. Every stop is traced.
- **Permission policy:** `ask_on_write`. Read-only work runs automatically; each write pauses for explicit approval/denial. Policies `auto` and `always_ask` are also implemented for testing.
- **Trust:** never execute document-embedded instructions, perform unrestricted filesystem access, run shell tools, send emails or expose environment secrets. Session scope is attached by the MCP client, not chosen by the LLM. No web tools.

## Three input-output success examples

1. **Input:** "What is the deadline in the uploaded sample project policy?" **Output:** "November 1, 2026 at 11:59 PM Yemen time" with the exact policy page reference. No invented current deadline.
2. **Input:** "When does the supplier have to deliver, and when is payment due?" **Output:** "Delivery by December 15, 2026; payment within 14 days of confirmed delivery after inspection" with citation and no fabricated calendar payment date.
3. **Input:** "Prepare a checklist of deliverables and save it." **Output:** Draft checklist with citations; the agent pauses at `save_report` and saves only if the human clicks **Approve**. Denial leaves database unchanged.

**Evaluation:** Five questions, persistence after restart, three hostile prompt-injection cases, and three JSONL traces (success, recovery and explicit failure). Test fixtures are labeled, not passed off as live-model runs.