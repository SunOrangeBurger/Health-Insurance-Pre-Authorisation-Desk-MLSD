# Local model selection

Selected: **qwen3:4b Q4_K_M**, non-thinking generation, 4096 context tokens, 512 generated-token ceiling, one loaded model and one global inference slot. Exact digest is in docs/evidence/model-qwen3.json. Application output is validated against policy evidence; generated prose is retained for audit while the UI shows the verified explanation.

The installed llama3.2:3b produced unreliable policy explanations. qwen2.5-coder:7b passed guarded decision scenarios, but initial sustained runs hit a host RAM limit. Investigation showed a runtime prompt-cache budget was the main cause; these runs do not prove the 7B model itself is inherently too large. Qwen3 4B also passed grounded approval/rejection, unfamiliar-procedure review, injection blocking, human precedent reuse, revocation and override. It is retained as the smaller local default.

The optional host prompt cache must be disabled with LLAMA_ARG_CACHE_RAM=0 before starting Ollama. Changing the environment after a server is already running does not apply the limit; restart that server. Non-mapped loading alone is insufficient. Memory/throughput claims come from the accompanying benchmark and soak artifacts, not model size estimates.

References: [official model catalog](https://ollama.com/library/qwen3), [runner cache report](https://github.com/ollama/ollama/issues/18264).
