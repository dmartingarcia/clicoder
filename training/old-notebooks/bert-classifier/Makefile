.PHONY: help venv install dataset train export-model clean jupyter

# Define el entorno virtual
VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
JUPYTER = $(VENV)/bin/jupyter

# Rutas
DATASET_DIR = ../csv_import_scripts/codiesp_csvs
MODEL_DIR = snapshots
NOTEBOOK = clasificador_jerarquico.ipynb

# Colores
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m

help:
	@echo "$(GREEN)═══════════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)  Entrenamiento de Modelo CIE-10 con BERT$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "$(YELLOW)Comandos disponibles:$(NC)"
	@echo "  $(GREEN)make setup$(NC)        - Configura todo (venv + dataset)"
	@echo "  $(GREEN)make venv$(NC)         - Crea entorno virtual"
	@echo "  $(GREEN)make install$(NC)      - Instala dependencias"
	@echo "  $(GREEN)make dataset$(NC)      - Descarga dataset CODIESP"
	@echo "  $(GREEN)make jupyter$(NC)      - Abre Jupyter Notebook"
	@echo "  $(GREEN)make train$(NC)        - Entrena el modelo (notebook completo)"
	@echo "  $(GREEN)make export-model$(NC) - Exporta modelo para ai_engine"
	@echo "  $(GREEN)make clean$(NC)        - Limpia entorno virtual"
	@echo ""

# Setup completo
setup: venv install dataset
	@echo "$(GREEN)✓ Setup completo! Ejecuta 'make jupyter' para entrenar$(NC)"

# Crear entorno virtual
$(VENV)/bin/activate:
	@echo "$(GREEN)Creando entorno virtual...$(NC)"
	@python3 -m venv $(VENV)
	@touch $(VENV)/bin/activate

venv: $(VENV)/bin/activate

# Instalar dependencias
install: venv
	@echo "$(GREEN)Instalando dependencias...$(NC)"
	@$(PIP) install -U pip setuptools wheel
	@$(PIP) install -r requirements.txt
	@echo "$(GREEN)✓ Dependencias instaladas$(NC)"

# Descargar dataset CODIESP
dataset:
	@echo "$(GREEN)Verificando dataset CODIESP...$(NC)"
	@if [ ! -d "$(DATASET_DIR)" ] || [ -z "$$(ls -A $(DATASET_DIR) 2>/dev/null)" ]; then \
		echo "$(YELLOW)Descargando dataset CODIESP...$(NC)"; \
		cd ../csv_import_scripts && make collect_codiesp; \
	else \
		echo "$(GREEN)✓ Dataset CODIESP ya existe$(NC)"; \
	fi

# Abrir Jupyter Notebook
jupyter: install
	@echo "$(GREEN)Abriendo Jupyter Notebook...$(NC)"
	@echo "$(YELLOW)Ejecuta todas las celdas del notebook para entrenar$(NC)"
	@$(JUPYTER) notebook $(NOTEBOOK)

# Entrenar modelo (ejecutar notebook completo - requiere nbconvert)
train: install dataset
	@echo "$(GREEN)Entrenando modelo...$(NC)"
	@if [ ! -f $(VENV)/bin/jupyter-nbconvert ]; then \
		$(PIP) install nbconvert; \
	fi
	@$(JUPYTER) nbconvert --to notebook --execute $(NOTEBOOK) --output $(NOTEBOOK)
	@echo "$(GREEN)✓ Entrenamiento completado$(NC)"
	@echo "$(GREEN)  Modelo guardado en: $(MODEL_DIR)/$(NC)"

# Exportar modelo para ai_engine
export-model:
	@echo "$(GREEN)Exportando modelo para ai_engine...$(NC)"
	@if [ ! -d "$(MODEL_DIR)" ]; then \
		echo "$(RED)✗ Error: No se encontró el modelo entrenado$(NC)"; \
		echo "$(YELLOW)  Ejecuta primero: make train$(NC)"; \
		exit 1; \
	fi
	@mkdir -p ../../ai_engine/model
	@echo "$(YELLOW)Copiando archivos del modelo...$(NC)"
	@cp -r $(MODEL_DIR)/* ../../ai_engine/model/
	@echo "$(GREEN)✓ Modelo exportado a ai_engine/model/$(NC)"

# Limpiar entorno
clean:
	@echo "$(YELLOW)Eliminando entorno virtual...$(NC)"
	@rm -rf $(VENV)
	@echo "$(GREEN)✓ Limpieza completada$(NC)"

# Limpiar todo (incluyendo modelo)
clean-all: clean
	@echo "$(YELLOW)Eliminando modelo entrenado...$(NC)"
	@rm -rf $(MODEL_DIR)
	@echo "$(GREEN)✓ Limpieza total completada$(NC)"
