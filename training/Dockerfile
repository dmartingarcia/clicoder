# Dockerfile para entorno de entrenamiento CIE-10
# Ubicación: training/Dockerfile
# Construir desde raíz: docker build -t cie10-training -f training/Dockerfile .
FROM cie10-ml-base:latest AS base

WORKDIR /home/cie10user

RUN pip3 install --no-cache-dir "datasets<4.0.0" # We need to stay below version 4.0.0 for compatibility with the Codiesp dataset, it has a script
RUN pip3 install --no-cache-dir grequests progressbar2
# papermill ejecuta los cuadernos volcando la salida de cada celda segun se produce.
# nbconvert no imprime nada hasta terminar, lo que deja un entrenamiento largo a ciegas.
RUN pip3 install --no-cache-dir papermill

# spaCy y sus modelos en español: los necesita el clasificador de diccionario, y sin ellos los
# bancos de pruebas que lo incluyen no se pueden ejecutar sobre GPU desde esta imagen.
RUN pip3 install --no-cache-dir "spacy>=3.7.0" && \
    python3 -m spacy download es_core_news_lg && \
    python3 -m spacy download es_dep_news_trf

# Copiar el código fuente de entrenamiento (contexto = training/)
COPY training/bert-classifier bert-classifier
COPY training/csv_import_scripts csv_import_scripts
COPY training/data_analysis data_analysis

# Crear usuario sin privilegios con UID/GID del host
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} cie10user 2>/dev/null || groupmod -n cie10user $(getent group ${GROUP_ID} | cut -d: -f1) 2>/dev/null || true && \
    useradd -u ${USER_ID} -g ${GROUP_ID} -ms /bin/bash cie10user 2>/dev/null || usermod -l cie10user -d /home/cie10user -m $(getent passwd ${USER_ID} | cut -d: -f1) 2>/dev/null || true && \
    mkdir -p /home/cie10user && \
    chown -R ${USER_ID}:${GROUP_ID} /home/cie10user
USER cie10user