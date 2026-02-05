# Dockerfile para AI Engine - FastAPI + Transformers
# Usa la imagen base compartida con CUDA
FROM cie10-ml-base:latest

WORKDIR /app

# Instalamos dependencias específicas de AI Engine
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias adicionales específicas de AI Engine
COPY ai_engine/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Instalar modelo de Spacy
RUN pip3 install https://github.com/explosion/spacy-models/releases/download/es_core_news_sm-3.8.0/es_core_news_sm-3.8.0-py3-none-any.whl

# Copiar código de la aplicación
COPY ai_engine/ .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
