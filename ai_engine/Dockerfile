# Dockerfile — CIE-10 AI Engine
# GPU path usa cie10-ml-base (CUDA 13.1 + flash-attn precompilados).
# CPU path usa python:3.11-slim (ligero, sin CUDA).
# Model weights are NOT baked in — mount the model directory at runtime:
#   docker run -v /path/to/model:/app/model -e MODEL_DIR=/app/model ...

# ARG must be declared before the first FROM to be usable in FROM instructions
ARG BUILD_WITH_CUDA=0

# ─── CPU base (lightweight) ──────────────────────────────────────────────────
FROM python:3.14-slim AS base-0

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

# ─── GPU base (flash-attn + CUDA 13.1 precompilados) ─────────────────────────
FROM cie10-ml-base:latest AS base-1

# ─── Select base via BUILD_WITH_CUDA (0=cpu, 1=gpu) ──────────────────────────
ARG BUILD_WITH_CUDA=0
FROM base-${BUILD_WITH_CUDA}

# Ubuntu solo tiene python3; asegurar alias python para compatibilidad
RUN python --version 2>/dev/null || ln -sf "$(which python3)" /usr/local/bin/python

WORKDIR /app

# ---- Python dependencies ----
COPY ai_engine/requirements.txt .

# CPU: install torch CPU wheel; GPU base already has torch+CUDA preinstalled
ARG BUILD_WITH_CUDA=0
RUN if [ "$BUILD_WITH_CUDA" = "0" ]; then \
        pip install --no-cache-dir \
            torch \
            --index-url https://download.pytorch.org/whl/cpu; \
    fi

RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download es_core_news_lg
RUN python -m spacy download es_dep_news_trf
ARG BUILD_WITH_CUDA=0
RUN if [ "$BUILD_WITH_CUDA" = "1" ]; then \
        pip install --no-cache-dir cupy-cuda13x; \
    fi

# ---- Application code ----
COPY ai_engine/ .

# ---- Runtime configuration ----
ENV MODEL_DIR=/app/model
ENV DEVICE=cpu
ENV HF_HOME=/cache/huggingface

RUN groupadd -g 1000 appuser && useradd -u 1000 -g appuser -m appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
