# Health Insurance Pre-Authorisation Desk: Project Doc Set

Mini Project 03, UE24AM342AA5 (ML System Design & AgentOps), PESU.

This folder is the complete brief for building the project with an AI coding agent
(Claude Code, Cursor, Aider, etc.) running on your laptop.

## Files, in reading order

| File | Purpose | Who reads it |
|---|---|---|
| `00_AGENT_PROMPT.md` | Master prompt. Paste this into the agent first. | Agent |
| `01_PROJECT_SPEC.md` | Every requirement (F/A/L/D) restated as a checklist with acceptance tests | Agent + you |
| `02_ARCHITECTURE.md` | Services, agent topology, data contract, stack, repo layout, deployment boundaries | Agent + you |
| `03_EXECUTION_PLAN.md` | Phased build order with exit criteria per phase | Agent |
| `04_EVAL_LOAD_DEMO.md` | Evaluation set design, metrics, SLO/load test method, demo script, report outline | Agent + you |

## How to use

1. Create a new empty git repo, e.g. `preauth-desk/`.
2. Copy this folder into it as `docs/brief/`.
3. Put the two corpus PDFs in `corpus/raw/` (policy wording and day-care list from ONE insurer, ONE retail product). Choose them yourself; see section "Corpus" in the spec. Get them from the insurer's website.
4. Get a free-tier LLM API key (Gemini, Groq, OpenRouter or similar). Set a spending limit on the account. Never commit it.
5. Open the agent in the repo root, then paste the contents of `00_AGENT_PROMPT.md` as the first message.
6. Let it work phase by phase. After each phase, run the phase's exit checks yourself before telling it to continue.

## Things only you can do

- Choose the insurer and product, and download the PDFs.
- Verify the cataract waiting-period clauses (spec 4.1) and confirm them at Evaluation 1.
- Supply the API key in a local `.env` (never in git).
- Run the final "clean clone" test on a second directory or machine.
- Fill the incident log with a real failure and be able to explain the code in the viva.

## Grading reminder

If `docker compose up` does not start a working system that serves a valid request at the demo, the score is **zero**. A working end-to-end path by week two is more valuable than breadth. Not all 22 requirements are expected; the priority order in `01_PROJECT_SPEC.md` is deliberate.
