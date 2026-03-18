# Dockerfile — CIE-10 AI Engine
# Self-contained: does NOT depend on cie10-ml-base.
# Model weights are NOT baked in — mount the model directory at runtime:
#   docker run -v /path/to/model:/app/model -e MODEL_DIR=/app/model ...

ARG BUILD_WITH_CUDA=0

FROM python:3.11-slim

# ---- System dependencies ----
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---- Python dependencies ----
COPY ai_engine/requirements.txt .

# Install PyTorch CPU wheel by default; override with CUDA wheel when
# the BUILD_WITH_CUDA build arg is set to "1".
ARG BUILD_WITH_CUDA=0
RUN if [ "$BUILD_WITH_CUDA" = "1" ]; then \
        pip install --no-cache-dir torch>=2.0.0; \
    else \
        pip install --no-cache-dir \
            torch>=2.0.0 \
            --index-url https://download.pytorch.org/whl/cpu; \
    fi

RUN pip install --no-cache-dir -r requirements.txt

# ---- Application code ----
COPY ai_engine/ .

# ---- Runtime configuration ----
ENV MODEL_DIR=/app/model
ENV DEVICE=cpu

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
