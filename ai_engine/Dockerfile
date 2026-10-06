ARG BUILD_WITH_CUDA=0

FROM python:3.11-slim AS base-0

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl wget build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

FROM cie10-ml-base:latest AS base-1

ARG BUILD_WITH_CUDA=0
FROM base-${BUILD_WITH_CUDA}

RUN python --version 2>/dev/null || ln -sf "$(which python3)" /usr/local/bin/python

WORKDIR /app

COPY ai_engine/requirements.txt .

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

COPY ai_engine/ .

ENV MODEL_DIR=/app/model
ENV DEVICE=cpu
ENV HF_HOME=/cache/huggingface

# uid fijo: la base CUDA ya usa el 1000 y un useradd sin -u caia en el 1001, sin permiso
# sobre la cache de HF montada del host (el servicio arrancaba pero sin modelo).
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
