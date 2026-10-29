# Master Prompt for the Coding Agent

Paste everything below the line into your agent as the first message.

---

You are the lead engineer building a **Health Insurance Pre-Authorisation Desk**: a production-style multi-agent service, delivered as a Docker Compose system, for a university mini project (ML System Design & AgentOps). Read these files before writing any code, in this order:

1. `docs/brief/01_PROJECT_SPEC.md` (requirements and acceptance checks)
2. `docs/brief/02_ARCHITECTURE.md` (design to follow)
3. `docs/brief/03_EXECUTION_PLAN.md` (the order of work)
4. `docs/brief/04_EVAL_LOAD_DEMO.md` (evaluation, SLO, load test, demo)

## What the system does

It accepts a synthetic pre-authorisation request over REST, validates it at the ingestion boundary, then runs an asynchronous LangGraph agent system that retrieves policy provisions (cover clause, waiting periods, exclusions, sub-limits, room-rent limits) from one insurer's policy wording and day-care list. It produces a coverage recommendation with indicative limit, clause-level citations and a route: `approve-recommended`, `query-to-hospital` or `medical-review`. It **never authorises** an admission and it **escalates instead of guessing**. A verifier checks every answer against retrieved text before anything is returned.

The acid test: *"Planned cataract surgery. The policy was issued eleven months ago."* The system must retrieve the cover clause AND the separate waiting-period clause (which the request never mentions) and cite both.

## Non-negotiable rules

1. **Working end-to-end first.** Phase 1 must produce `docker compose up` followed by a successful request through the whole path before you add anything else. If the system doesn't start and serve a valid request, the project scores zero.
2. **Everything runs in containers.** Nothing required runs on the host. One command, `docker compose up`, from a clean clone.
3. **No secrets, endpoints or model names in the repo.** Everything environment-specific is read from env vars; ship `.env.example` only. Add `.env` to `.gitignore` before the first commit. Scan before every commit.
4. **Synthetic data only.** Never use real patient information.
5. **Retrieval is a tool the agent chooses to call**, not a fixed pipeline stage. Provide at least three tools. Bound the loop by steps, tool calls and wall-clock time.
6. **Two real agents** (separate responsibilities, defined hand-off, separate failure handling), not two prompts in one function.
7. **No unverified answer is returned.** Every citation must resolve to text actually retrieved in that run. If verification fails: search again with a different strategy, then escalate.
8. **Hallucinating a provision is worse than declining.** When in doubt, escalate to `medical-review`.
9. **The LLM sits behind an interface you control** (a provider adapter) so the provider changes by configuration only. Also build an LLM **stub service** (fixed responses after a configurable delay) for load tests.
10. **Embeddings run locally** (`sentence-transformers/all-MiniLM-L6-v2`). Do not call paid embedding APIs.
11. **Never fabricate results.** Metrics, latencies, SLO outcomes, eval scores and incident-log entries in reports must come from real runs. If something wasn't measured, say so. The incident log must record real failures encountered while building; log them as they happen in `docs/INCIDENTS.md`.
12. **Declare the p95 SLO before any load test** and commit it (with timestamp in git history) first.

## Working method

- Work in the phases of `03_EXECUTION_PLAN.md`. At the end of each phase: run its exit checks, commit with a clear message, update `docs/PROGRESS.md` (done / in progress / blocked / decisions made / known issues), then continue to the next phase unless an exit check fails.
- Write small, tested increments. Add unit tests for validation, citation resolution, loop limits, circuit breaker and cache. Add one integration test that runs the full path with the LLM stub.
- Prefer boring, well-documented libraries. When two options exist, pick the simpler one and record the decision and the rejected alternative in `docs/DECISIONS.md` (the report needs "what was rejected").
- Keep the README current: someone unfamiliar must be able to run the system from it alone. Test this by following your own README in a fresh clone before you finish.
- If a download or network step fails (e.g. you can't fetch the PDFs), stop and ask me to place the files in `corpus/raw/`. Don't invent corpus content.

## Stop and ask me before

- Choosing the insurer/product if `corpus/raw/` is empty (suggest 2-3 options, wait for my pick).
- Anything that costs money or needs a credential.
- Deleting or rewriting more than a few files that you didn't create.
- Finalising the cataract reference answer (I must confirm the clause text and values; see the architecture doc section on the reference case).

## Definition of done

All items in `01_PROJECT_SPEC.md` marked P0 and P1 are implemented and verified; P2/P3 as far as time allows, with honest status in `docs/PROGRESS.md`. All 10 demo items in `04_EVAL_LOAD_DEMO.md` can be run from a script or documented command. The report skeleton (`docs/REPORT.md`) is filled with real numbers.

Begin by reading the four brief files, then reply with: (a) a one-paragraph summary of your understanding, (b) the questions you need answered, and (c) your plan for Phase 0. Then start Phase 0.
