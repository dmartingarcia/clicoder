# Dockerfile: CIE-10 AI Engine
# GPU path usa cie10-ml-base (CUDA 13.1 + flash-attn precompilados).
# CPU path usa python:3.11-slim (ligero, sin CUDA).
# Model weights are NOT baked in: mount the model directory at runtime:
#   docker run -v /path/to/model:/app/model -e MODEL_DIR=/app/model ...

# ARG must be declared before the first FROM to be usable in FROM instructions
ARG BUILD_WITH_CUDA=0

# ─── CPU base (lightweight) ──────────────────────────────────────────────────
FROM python:3.11-slim AS base-0

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl wget build-essential cmake \
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

RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download es_core_news_lg
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

# El uid se fija a proposito. La base CUDA ya trae un usuario en el 1000, asi que un useradd
# sin -u caia en el 1001 y el contenedor no podia escribir en la cache de Hugging Face montada
# desde el host, que es del 1000. El sintoma era enganoso: el servicio arrancaba y respondia,
# pero sin modelo, porque la descarga fallaba con un permiso denegado.
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN if getent passwd ${USER_ID} >/dev/null; then userdel -r "$(getent passwd ${USER_ID} | cut -d: -f1)" 2>/dev/null || true; fi && \
    if getent group ${GROUP_ID} >/dev/null; then groupdel "$(getent group ${GROUP_ID} | cut -d: -f1)" 2>/dev/null || true; fi && \
    groupadd -g ${GROUP_ID} appuser && useradd -u ${USER_ID} -g appuser -m appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "75", "--no-access-log"]
