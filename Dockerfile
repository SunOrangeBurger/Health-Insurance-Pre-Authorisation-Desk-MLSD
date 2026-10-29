# Multi-stage Dockerfile for Health Insurance Pre-Authorisation Desk
# Command switch: api | worker | ingest | stub

FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final Runtime Image
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root user and directories
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser \
    && mkdir -p /app/corpus/raw /app/index_data /app/evals/results /app/loadtest/results \
    && chown -R appuser:appuser /app

# Copy application source and assets
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY contracts/ ./contracts/
COPY prompts/ ./prompts/
COPY web/ ./web/
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/entrypoint.sh \
    && pip install --no-cache-dir -e . \
    && chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

EXPOSE 8000 8080

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["api"]
