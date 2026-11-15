# Local benchmark attempt — 2026-11-15

Status: resource-guard stop; capacity acceptance remains incomplete.

The real-model test used qwen2.5-coder:7b, one shared inference slot, and authenticated Locust hospital sessions. Three workers reached readiness, but Windows available RAM fell below max(2 GiB, 15% physical RAM) for 30 seconds. Load was stopped; two extra replicas were removed. Recovery was also stopped while RAM remained low. The supervisor now checks the reserve before starting any stage or recovery.

| Run | Completed observations | Failures observed | p50 ms | p95 ms | p99 ms | Unobserved assessments | Minimum RAM GiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| workers3-users1 | 3 | 0 | 5100 | 12000 | 12000 | 1 | 1.19 |
| workers3-recovery | 2 | 0 | 6200 | 6200 | 6200 | 1 | 0.84 |

These tiny, interrupted samples cannot establish p95/p99 reliability, sustainable throughput, scaling benefit, or a passed SLO. Zero observed failures does not include the unobserved in-flight assessments. No stress escalation or soak was completed.

Three workers shared the same local model budget; more workers are not more model capacity. The application has been returned to one worker. Freeing RAM or choosing a lighter validated deployment is required before continuing real-model capacity tests.

Raw JSON/CSV evidence is under loadtest/results/desk. The supervisor records CPU/RAM samples and Redis queue depth/oldest age and stops if monitoring fails. Login is shared across virtual users for processing-capacity tests; authentication-rate-limit performance is a separate concern.
