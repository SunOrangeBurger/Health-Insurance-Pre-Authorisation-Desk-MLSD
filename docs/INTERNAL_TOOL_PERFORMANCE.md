# Internal desk performance and limitations

Measured November 17, 2026 on a 16 GB Windows laptop with RTX 4050 6 GB. Docker Engine runs in Ubuntu WSL; bounded Windows Ollama runs Qwen3 4B Q4_K_M, context 4096, output 512, thinking disabled and host prompt cache disabled. One inference slot is shared across replicas. The model was already warm; these stages do not measure cold startup. All requests and accounts are synthetic.

## Load, saturation and recovery

Each load stage sent a three-minute mixed browse/submit workload, then allowed in-flight assessments to drain. Throughput below includes that observed completion interval. Virtual users shared a seeded login, so these results exclude login-rate capacity and human review time. Non-inference API endpoint percentiles passed p95 <= 1 second and p99 <= 2 seconds in the one-worker stages.

| Stage | Assessments | Errors | p50 s | p95 s | p99 s | Assessments/s |
|---|---:|---:|---:|---:|---:|---:|
| workers1-users2 | 27 | 0 | 4.1 | 7.1 | 7.1 | 0.151 |
| workers1-users4 | 53 | 0 | 6.2 | 10 | 11 | 0.291 |
| workers1-users8 | 61 | 0 | 16 | 23 | 25 | 0.310 |
| workers1-users16 | 71 | 0 | 40 | 47 | 49 | 0.318 |
| workers1-recovery | 6 | 0 | 3.1 | 5.1 | 5.1 | 0.105 |

The eight-user workload passed the declared machine p95 <= 30 seconds and p99 <= 60 seconds targets at about 0.310 assessments/second. Sixteen users saturated the serial model budget: p95 reached 47 seconds, despite no observed errors or resource stop. Recovery returned p95 to 5.1 seconds. These are exploratory single-run local observations, not a statistical capacity guarantee. Histograms with fewer than 100 samples provide weak p99 evidence.

Exact-ID database timing at eight users: queue wait p50 12.737s/p95 20.757s/p99 22.104s; model assessment p50 2.686s/p95 3.170s/p99 3.890s. Retrieval tool p95 was 0.000524s with the warmed index/cache. Database completion and Locust polling times differ, and their percentile methods differ. Queue pressure dominates the end-to-end tail.

## One versus three workers

At four virtual users and the same global inference budget, one worker completed 53 assessments with no errors at 0.291 assessments/second (p95 10s). Three workers completed 52 observations with one degraded failure at 0.279 assessments/second (p95 11s). The 1.9% failure rate fails the error target. Three-worker recovery completed four assessments without error. There is no demonstrated throughput benefit; more replicas use more RAM and can contend for the bounded ten-second inference-slot acquisition. Logs for the degraded case show no model call, consistent with that contention; the existing error log does not retain the exception class, so this root cause is an inference.

Use one worker on this machine. Increasing worker replicas alone cannot multiply the single model's capacity. Scale model-serving capacity and validate again before claiming a higher supported arrival rate. The earlier 3.22x stub scaling result applies only to its separate workload.

## Five-minute mixed stability check

The user shortened the required soak from 30 to five minutes due to time constraints. The test uses 0.1859 assessments/second, approximately 60% of the passing eight-user rate. It mixes nominal cataract cases, unserved waiting periods, unsupported procedures and prompt injection, using one temporary synthetic human-approved precedent. The full run passed: 56 assessments, zero failures or unobserved cases, p50 4.1s, p95 7.1s and p99 7.2s. Achieved rate including supervisor startup/drain was 0.1851/s. There were 34 automatic approvals, 20 exception cases sent to review (nine waiting-period, seven unsupported-procedure and four injection cases), and two nominal cases conservatively left for review. No exceptional case was approved. The temporary precedent was revoked afterward. These are fixture outcome counts, not an estimate of clinical accuracy.

The memory comparison used 60–120 seconds after start versus the final sampled minute: API mean RSS grew 0.017%, worker RSS 0.102%, and model runner RSS decreased. Queue depth peaked at two and age at 8.19s; minimum free host RAM was 3.88 GiB, sampled peak GPU memory 3301 MiB, sampled peak host CPU 23.4%. The monitor sampled 297 seconds of the 300-second Locust workload (302.5 seconds supervisor elapsed); its five-second cadence leaves a normal final sampling gap. Runtime acceptance uses elapsed time while retaining this coverage gap explicitly. Optional 30-minute and two-hour profiles remain available.

## Evidence and boundaries

Raw stage JSON/CSV files: loadtest/results/desk/2026-11-17-freed and 2026-11-17-workers3. Phase sidecars use exact case IDs rather than joining across Windows/WSL wall clocks. The one-worker load run predates the Redis-clock queue-age correction; its queue-age samples understate age by roughly the host/WSL offset. Exact database queue-duration percentiles remain valid. Later runs use Redis time for queue-age guarding. Host CPU/RAM and GPU samples include other applications and are sampled values, not continuous peaks.

Earlier RAM-guard stops and the invalid missing-credential attempt remain retained and excluded from capacity passes. Synthetic model-quality and semantic fixtures are small; held-out semantic positive recall is only 50%. Policy explanations are verified deterministically, model prose is audit-only, and uncertain cases go to human review. This demonstrates an internal decision-support workflow; it is not validated for real clinical or insurer use. Human turnaround and reviewer throughput were not simulated in these capacity runs; their functional paths were tested separately.

## Short stability run component timings

Database durations below use exact case IDs; no host/WSL clock alignment is assumed. Automatic-final timing has 34 observations; inference excludes the four injection cases blocked before model access. Retrieval counts individual tool calls.

| Phase | Samples | p50 s | p95 s | p99 s |
|---|---:|---:|---:|---:|
| automatic_final_seconds | 34 | 4.4930 | 7.6834 | 7.9893 |
| ollama_assessment_seconds | 52 | 2.4805 | 3.1557 | 3.8646 |
| queue_wait_seconds | 56 | 0.4068 | 3.5750 | 6.4932 |
| retrieval_tool_seconds | 357 | 0.0001 | 0.0005 | 0.0027 |
| submission_to_terminal_seconds | 56 | 3.7694 | 7.6547 | 8.7650 |
| worker_seconds | 56 | 2.5413 | 5.8985 | 6.0831 |

The final queue-cap addition was deployed after these performance measurements. Its threshold of 64 queued/running jobs is above the largest measured depth of 16; it was separately verified with concurrent-admission and full-queue workflow tests, and deployed functional acceptance. No throughput claim is made for overload above that cap. Full desk queues produce a failed assessment visible for human review; the legacy submission endpoint returns 503.
