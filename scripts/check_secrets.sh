#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo " Running Secrets & Model Name Scan..."
echo "=========================================================="

FAILED=0

# 1. Check that .env is not tracked in git
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
    echo "[FAIL] .env file is tracked in git! Untrack it immediately."
    FAILED=1
else
    echo "[PASS] .env is not tracked in git."
fi

# 2. Check for common API key and private key signatures
PATTERNS=(
    'sk-[a-zA-Z0-9]{20,}'
    'sk-ant-[a-zA-Z0-9_-]{20,}'
    'AIza[0-9A-Za-z_-]{35}'
    'ghp_[a-zA-Z0-9]{36}'
    'gho_[a-zA-Z0-9]{36}'
    'BEGIN (RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY'
)

for PATTERN in "${PATTERNS[@]}"; do
    MATCHES=$(git grep -EI -e "${PATTERN}" -- ':!scripts/check_secrets.sh' || true)
    if [ -n "${MATCHES}" ]; then
        echo "[FAIL] Found secret pattern match (${PATTERN}):"
        echo "${MATCHES}"
        FAILED=1
    fi
done

# 3. Check for credentials embedded in URLs
URL_CRED_MATCHES=$(git grep -EI -e 'https?://[a-zA-Z0-9_.-]+:[a-zA-Z0-9_.-]+@' -- ':!scripts/check_secrets.sh' ':!.env.example' || true)
if [ -n "${URL_CRED_MATCHES}" ]; then
    echo "[FAIL] Found URL with hardcoded credentials:"
    echo "${URL_CRED_MATCHES}"
    FAILED=1
else
    echo "[PASS] No hardcoded credentials in URLs."
fi

# 4. Check for hardcoded model names in src/
# Rule: Everything environment-specific is read from env vars
MODEL_PATTERNS=(
    'gpt-3\.5'
    'gpt-4'
    'claude-3'
    'claude-2'
    'gemini-1\.5'
    'gemini-pro'
    'text-embedding-ada'
    'llama-3'
    'mistral-7b'
)

if [ -d "src" ] && [ "$(ls -A src 2>/dev/null)" ]; then
    for M_PAT in "${MODEL_PATTERNS[@]}"; do
        M_MATCHES=$(git grep -EI -e "${M_PAT}" src/ 2>/dev/null || true)
        if [ -n "${M_MATCHES}" ]; then
            echo "[FAIL] Found hardcoded model name in src/ (${M_PAT}):"
            echo "${M_MATCHES}"
            FAILED=1
        fi
    done
fi

if [ ${FAILED} -eq 0 ]; then
    echo "[PASS] All secret and configuration hygiene checks passed successfully!"
    exit 0
else
    echo "[FAIL] Secret check failed. Remove credentials / hardcoded values before proceeding."
    exit 1
fi
