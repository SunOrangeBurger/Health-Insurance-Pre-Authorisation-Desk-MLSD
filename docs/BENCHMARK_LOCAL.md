# Local benchmark status

## Final status — 2026-11-17

**100% of the user-adjusted demonstration scope is complete.** The user shortened the required soak to five minutes. That test passed with 56 assessments, zero errors or unobserved cases, p50 4.1s/p95 7.1s/p99 7.2s, 34 automatic approvals and all 20 exceptional cases sent to review. The nominal eight-user stage passed at about 0.310 assessments/second; 16 users saturated the p95 target. Three workers failed the error target (one degraded observation out of 52) without increasing throughput. One worker remains deployed. See INTERNAL_TOOL_PERFORMANCE.md for the full report and raw evidence. Longer soak reliability is unverified.

## Earlier resumed attempts — 2026-11-17

At this earlier point, verified completion remained **85%**. Qwen3 4B with disabled host prompt cache remains stable near 720 MB runner RSS. The first resumed two-user attempt stopped after 57 seconds on the host RAM guard. A subsequent retry with valid benchmark credentials completed 20 assessments with zero observed failures, p50 4.1 seconds and p95/p99 7.2 seconds, but stopped after 123 seconds when available RAM fell to about 1.15 GiB. One accepted assessment was unobserved by the stopped client. Recovery was refused below the reserve. Browser processes accounted for several GB at inspection; user applications were left running.

The intermediate `2026-11-17-retry` directory is an invalid attempt: the new shell lacked `DESK_HOSPITAL_PASSWORD`, so virtual users could not start. It was interrupted and must not be used for capacity claims. A new CLI preflight rejects that missing configuration before starting load.

Raw artifacts: `loadtest/results/desk/2026-11-17` and `2026-11-17-capacity`. Consolidated results: LOAD_STRESS_RESULTS.md. No higher-load stage, matched one-versus-three-worker comparison or full 30-minute soak has passed. The available partial samples cannot establish sustainable throughput. Further runs require sufficient free host memory.

## Earlier attempt — 2026-11-15

Status: resource-guard stop; capacity acceptance remains incomplete.

The real-model test used qwen2.5-coder:7b, one shared inference slot, and authenticated Locust hospital sessions. Three workers reached readiness, but Windows available RAM fell below max(2 GiB, 15% physical RAM) for 30 seconds. Load was stopped; two extra replicas were removed. Recovery was also stopped while RAM remained low. The supervisor now checks the reserve before starting any stage or recovery.

| Run | Completed observations | Failures observed | p50 ms | p95 ms | p99 ms | Unobserved assessments | Minimum RAM GiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| workers3-users1 | 3 | 0 | 5100 | 12000 | 12000 | 1 | 1.19 |
| workers3-recovery | 2 | 0 | 6200 | 6200 | 6200 | 1 | 0.84 |

These tiny, interrupted samples cannot establish p95/p99 reliability, sustainable throughput, scaling benefit, or a passed SLO. Zero observed failures does not include the unobserved in-flight assessments. No stress escalation or soak was completed.

Three workers shared the same local model budget; more workers are not more model capacity. The application has been returned to one worker. Freeing RAM or choosing a lighter validated deployment is required before continuing real-model capacity tests.

Raw JSON/CSV evidence is under loadtest/results/desk. The supervisor records CPU/RAM samples and Redis queue depth/oldest age and stops if monitoring fails. Login is shared across virtual users for processing-capacity tests; authentication-rate-limit performance is a separate concern.
