# Incident & Real Failure Log

This log records **genuine failures and issues** encountered during development, testing, and deployment — not invented entries. Each entry documents: date/time, symptom, detection, root cause, fix, and prevention.

> Per project rule 11: "The incident log must record real failures encountered while building; log them as they happen." The viva requires at least one genuine entry with the ability to explain the code.

---

## INC-001 — git root outside project directory (2026-10-29, Phase 0)

| Field | Detail |
|---|---|
| **Date** | 2026-10-29 T ~11:14 IST |
| **Phase** | Phase 0 |
| **Symptom** | Running `git status` inside `mlsd-mini-project/` showed untracked files from the entire `~/Projects/` directory, including dozens of unrelated projects. |
| **Detection** | `git rev-parse --show-toplevel` returned `/home/arunhariharan/Projects` instead of `/home/arunhariharan/Projects/mlsd-mini-project`. |
| **Root Cause** | A `.git/` directory existed at `~/Projects/` (a parent-level repository), causing git to treat `mlsd-mini-project/` as a subdirectory of that repo rather than its own repository. |
| **Fix** | Ran `git init` inside `mlsd-mini-project/` to create a project-local `.git/`, then `git branch -m main` to rename the default branch. This shadowed the parent repo for all operations within the project directory. |
| **Prevention** | Always verify `git rev-parse --show-toplevel` equals the intended project root before the first commit. Add to Phase 0 exit checklist. |

---

## INC-002 — `check_secrets.sh` regex syntax error with `git grep` (2026-10-29, Phase 0)

| Field | Detail |
|---|---|
| **Date** | 2026-10-29 T ~11:17 IST |
| **Phase** | Phase 0 |
| **Symptom** | `./scripts/check_secrets.sh` printed `fatal: command line, 'AIza[0-9A-Za-z-_]{35}': Invalid range end` and `error: unknown option '--BEGIN (RSA|EC|...)`. Script exited 0 despite errors because the failure wasn't caught in the `FAILED` guard. |
| **Detection** | Running `make check-secrets` for the first time immediately after creation. |
| **Root Cause** | Two issues: (1) `git grep -EI` treats `[a-zA-Z-_]` as having an invalid range because `-` is not escaped (must be `[a-zA-Z_-]` or `\-`). (2) The `-----BEGIN PRIVATE KEY-----` pattern was passed as a positional argument rather than via `-e`, causing git to interpret the leading `--` as an option flag. |
| **Fix** | Rewrote all `git grep` calls to use `-e "${PATTERN}"` (explicit expression flag). Fixed the character class to use `[a-zA-Z_-]` ordering (dash at end). Split the private key pattern to avoid the leading `--`. |
| **Prevention** | Always test secret scan scripts on a repo with staged files before committing. Add a CI-style self-test that runs `check_secrets.sh` and asserts exit code 0 as part of the pre-commit hook. |

---

## INC-003 — `docker` command not found; container runtime unavailable (2026-10-29, Phase 0)

| Field | Detail |
|---|---|
| **Date** | 2026-10-29 T ~11:12 IST |
| **Phase** | Phase 0 |
| **Symptom** | `docker --version` returned `bash: docker: command not found`. `docker compose version` also failed. |
| **Detection** | First attempt to verify container tooling during Phase 0 setup. |
| **Root Cause** | Docker CE is not installed on the development machine. Only **Podman 5.8.9** is installed, which is Docker-compatible but uses a different binary name. `podman compose` requires an external compose provider (`docker-compose` or `podman-compose`) which was also absent. |
| **Fix** | Installed **podman-compose 1.6.0** via `uv tool install podman-compose`. Created `~/.local/bin/docker` → `/usr/bin/podman` and `~/.local/bin/docker-compose` → `$(which podman-compose)` symlinks. All `docker`/`docker-compose` commands in the `Makefile` now resolve transparently. |
| **Prevention** | Document the Podman symlink setup in `README.md` under Prerequisites. Add a `make check-env` target that verifies `docker` and `docker-compose` resolve before `make build`. Record in ADR-006. |

---

*(Real incidents encountered in future phases will be appended here as they occur.)*

---

## INC-004 — incompatible Redis client pins blocked dependency resolution (2026-11-06, Phase 1)

| Field | Detail |
|---|---|
| **Date** | 2026-11-06 |
| **Phase** | Phase 1 |
| **Symptom** | `uv pip install` reported that the dependency set was unsatisfiable. |
| **Detection** | Creation of the Python 3.11 verification environment before running Phase 1 tests. |
| **Root Cause** | `arq==0.26.0` requires the Python Redis client below version 5, but the project pinned `redis==5.0.7`. |
| **Fix** | Changed the Python client pin to `redis==4.6.0`; kept the Redis server image at version 7. |
| **Prevention** | Resolve the complete pinned dependency set in CI, not only individual package versions. |

---

## INC-005 — Podman build duplicated the app image and pulled CUDA dependencies (2026-11-06, Phase 1)

| Field | Detail |
|---|---|
| **Date** | 2026-11-06 |
| **Phase** | Phase 1 |
| **Symptom** | Compose launched three parallel builds of the same image and pip began downloading several hundred megabytes of CUDA libraries for a CPU-only system. |
| **Detection** | First full `docker compose build` after implementing the walking skeleton. |
| **Root Cause** | Each service declared its own anonymous `build`, and `sentence-transformers` left PyTorch unconstrained. |
| **Fix** | Reused one named application image across API, worker and stub; pinned the CPU-only PyTorch wheel. |
| **Prevention** | Explicitly pin CPU/GPU variants for ML runtimes and ensure services sharing a Dockerfile also share an image tag. |

---

## INC-006 — Podman rejected short base-image names during non-interactive startup (2026-11-06, Phase 1)

| Field | Detail |
|---|---|
| **Date** | 2026-11-06 |
| **Phase** | Phase 1 |
| **Symptom** | `docker compose up -d` failed with `short-name resolution enforced but cannot prompt without a TTY`. |
| **Detection** | First Compose startup after a successful application image build. |
| **Root Cause** | PostgreSQL and Redis used unqualified image names, which Podman would not resolve non-interactively. |
| **Fix** | Changed them to `docker.io/library/postgres:16-alpine` and `docker.io/library/redis:7-alpine`. |
| **Prevention** | Use fully qualified public image references in Compose files intended to support both Docker and Podman. |
