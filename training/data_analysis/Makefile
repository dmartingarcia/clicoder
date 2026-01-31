.PHONY: venv install clean jupyter

# Variables
VENV_NAME := .venv
PYTHON := python3
PIP := $(VENV_NAME)/bin/pip
JUPYTER := $(VENV_NAME)/bin/jupyter
PYTHON_VENV := $(VENV_NAME)/bin/python

# Rutas de archivos
REQUIREMENTS := requirements.txt

# Crear entorno virtual
venv:
	@echo "Creando entorno virtual $(VENV_NAME)..."
	@$(PYTHON) -m venv $(VENV_NAME)
	@$(PIP) install --upgrade pip
	@echo "Entorno virtual creado en $(VENV_NAME)"

# Instalar dependencias
install: venv
	@echo "Instalando dependencias desde $(REQUIREMENTS)..."
	@$(PIP) install -r $(REQUIREMENTS)
	@echo "Dependencias instaladas correctamente"
	@echo "Para activar el entorno virtual, ejecuta: source $(VENV_NAME)/bin/activate"

# Descargar recursos de NLTK
nltk: install
	@echo "Descargando recursos de NLTK..."
	@$(PYTHON_VENV) -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet');"
	@echo "Recursos de NLTK descargados correctamente"

# Iniciar Jupyter Notebook
jupyter: install
	@echo "Iniciando Jupyter Notebook..."
	@$(JUPYTER) notebook

# Iniciar JupyterLab
jupyterlab: install
	@echo "Iniciando JupyterLab..."
	@$(JUPYTER) lab

# Limpiar entorno virtual y cache
clean:
	@echo "Eliminando entorno virtual $(VENV_NAME)..."
	@rm -rf $(VENV_NAME)
	@echo "Entorno virtual eliminado"
	@rm -rf cache

# Mostrar ayuda
help:
	@echo "Makefile para gestionar el entorno de análisis de datos CIE-10"
	@echo ""
	@echo "Comandos disponibles:"
	@echo "  make venv        - Crear entorno virtual"
	@echo "  make install     - Instalar dependencias en el entorno virtual"
	@echo "  make nltk        - Descargar recursos necesarios de NLTK"
	@echo "  make jupyter     - Iniciar Jupyter Notebook"
	@echo "  make jupyterlab  - Iniciar JupyterLab"
	@echo "  make clean       - Eliminar entorno virtual y cache"
	@echo "  make help        - Mostrar esta ayuda"
	@echo ""
	@echo "Uso típico:"
	@echo "  make install     # Crear entorno e instalar dependencias"
	@echo "  make jupyterlab  # Iniciar JupyterLab para trabajar con notebooks"

# Comando predeterminado
.DEFAULT_GOAL := help