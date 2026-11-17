# Local load and stress results

Real Ollama with one global inference slot. Root/nommap attempts used the 7B model; qwen3/cache0 profiles used Qwen3 4B. Profile metadata records the exact configuration. Virtual users share a seeded hospital login; login capacity and human turnaround are excluded.

| Stage | Observations | Failed | Unobserved | p50 s | p95 s | p99 s | Assessment/s | Min free RAM GiB | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-11-17/workers1-users2 | 5 | 0 | 1 | 6.20 | 8.20 | 8.20 | 0.099 | 1.62 | guard stopped |
| 2026-11-17-capacity/workers1-users2 | 20 | 0 | 1 | 4.10 | 7.20 | 7.20 | 0.171 | 1.15 | guard stopped |
| 2026-11-17-freed/workers1-users16 | 71 | 0 | 0 | 40.00 | 47.00 | 49.00 | 0.318 | 4.14 | completed |
| 2026-11-17-freed/workers1-users2 | 27 | 0 | 0 | 4.10 | 7.10 | 7.10 | 0.151 | 4.62 | completed |
| 2026-11-17-freed/workers1-users4 | 53 | 0 | 0 | 6.20 | 10.00 | 11.00 | 0.291 | 4.56 | completed |
| 2026-11-17-freed/workers1-users8 | 61 | 0 | 0 | 16.00 | 23.00 | 25.00 | 0.310 | 4.58 | completed |
| 2026-11-17-workers3/workers3-users4 | 52 | 1 | 0 | 4.10 | 11.00 | 12.00 | 0.279 | 3.18 | failed exit |
| cache0/workers1-users1 | 15 | 0 | 0 | 4.10 | 5.20 | 5.20 | 0.084 | 4.60 | completed |
| nommap/workers1-users1 | 14 | 0 | 0 | 5.10 | 6.20 | 6.20 | 0.078 | 2.27 | completed |
| nommap/workers1-users2 | 0 | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.000 | 2.20 | guard stopped |
| qwen3/workers1-users1 | 3 | 0 | 0 | 4.10 | 4.10 | 4.10 | 0.086 | 1.21 | guard stopped |
| qwen3-shape/workers1-users1 | 7 | 0 | 1 | 3.10 | 5.10 | 5.10 | 0.109 | 0.98 | guard stopped |
| workers1-users1 | 14 | 0 | 1 | 5.10 | 10.00 | 10.00 | 0.078 | 3.76 | completed |
| workers1-users2 | 21 | 0 | 2 | 6.20 | 8.20 | 10.00 | 0.160 | 1.74 | guard stopped |
| workers3-users1 | 3 | 0 | 1 | 5.10 | 12.00 | 12.00 | 0.047 | 1.19 | guard stopped |
| 2026-11-17/workers1-recovery | 0 | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.000 | 1.92 | guard stopped |
| 2026-11-17-capacity/workers1-recovery | 0 | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.000 | 1.29 | guard stopped |
| 2026-11-17-freed/workers1-recovery | 6 | 0 | 0 | 3.10 | 5.10 | 5.10 | 0.105 | 4.16 | completed |
| 2026-11-17-workers3/workers3-recovery | 4 | 0 | 0 | 4.10 | 4.10 | 4.10 | 0.069 | 3.25 | completed |
| nommap/workers1-recovery | 0 | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.000 | 2.19 | guard stopped |
| qwen3/workers1-recovery | 0 | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.000 | 0.99 | guard stopped |
| qwen3-shape/workers1-recovery | 0 | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.000 | 0.98 | guard stopped |
| workers1-recovery | 0 | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.000 | 1.82 | guard stopped |
| workers3-recovery | 2 | 0 | 1 | 6.20 | 6.20 | 6.20 | 0.069 | 0.84 | guard stopped |

Percentiles use Locust histogram buckets. Small samples, especially fewer than 100 assessments, cannot establish a robust p99. Guard-stopped runs and unobserved assessments are never reported as passing. Initial model loading may be included; no inference warmup is removed retroactively.

A completed stage is an observation, not a claim that all SLOs passed. Machine assessment includes queue wait and polling overhead; dashboard worker processing excludes queue wait. Human approval latency is excluded. Soak testing is separate and is not established by these stages.
