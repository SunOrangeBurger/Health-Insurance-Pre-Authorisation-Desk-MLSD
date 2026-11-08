# End-to-End Service Level Objective

**Declared:** 2026-11-08 12:10 IST, before any project load-test measurement.

## Service-level indicator

Elapsed wall-clock time from a successful `POST /v1/preauth` acceptance until the corresponding run first reaches a terminal status: `completed`, `escalated`, `degraded`, or `failed`.

The measurement includes queue delay, provider latency, retrieval, verification, persistence and polling visibility. It does not use the POST response latency as a substitute for completed-run latency.

## Objective

With the local stub provider configured for 250 ms base delay and up to 50 ms jitter:

- p95 end-to-end completion latency **≤ 10 seconds** at **10 concurrent users**;
- terminal-run error rate **< 1%**;
- no run may return a confident recommendation after incomplete verification.

## Rationale

The brief requires an answer within minutes. A 10-second p95 target for the deterministic local/stub deployment leaves substantial budget for a slower real provider while keeping the synthetic desk interaction responsive. Ten concurrent users represents a small TPA desk rather than internet-scale traffic. The agent has a long-tail risk from queueing, CPU embedding/retrieval and provider retries, so p95—not mean latency—is the primary measure.

The SLO applies to this development machine and configuration. Later results must record CPU, memory, worker count and stub settings, identify the first tested concurrency that misses the target, and must not be generalized to production hardware.

## Error definition

An error is a submission or terminal-state failure caused by the system under test. Deliberately malformed requests used to verify quarantine are reported separately and do not count against the valid-run SLO. Safe `escalated` and `degraded` outcomes are successful terminal responses when their triggering condition is intentional.
