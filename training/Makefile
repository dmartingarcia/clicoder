.PHONY: help setup dataset train export clean

GREEN = \033[0;32m
YELLOW = \033[1;33m
BLUE = \033[0;34m
NC = \033[0m

help:
	@echo "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@echo "$(BLUE)  Sistema de Entrenamiento CIE-10$(NC)"
	@echo "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "$(YELLOW)Pipeline completo:$(NC)"
	@echo "  $(GREEN)make all$(NC)          - Ejecuta todo (setup + train + export)"
	@echo ""
	@echo "$(YELLOW)Comandos individuales:$(NC)"
	@echo "  $(GREEN)make setup$(NC)        - Configura entorno de entrenamiento"
	@echo "  $(GREEN)make dataset$(NC)      - Descarga dataset CODIESP"
	@echo "  $(GREEN)make train$(NC)        - Entrena el modelo"
	@echo "  $(GREEN)make jupyter$(NC)      - Abre Jupyter para entrenar manualmente"
	@echo "  $(GREEN)make export$(NC)       - Exporta modelo a ai_engine"
	@echo "  $(GREEN)make clean$(NC)        - Limpia entornos virtuales"
	@echo ""

# Pipeline completo: setup -> dataset -> entrenamiento -> exportar
all: setup train export
	@echo "$(GREEN)════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)  ✓ Pipeline completo finalizado$(NC)"
	@echo "$(GREEN)  Modelo entrenado y exportado a ai_engine/$(NC)"
	@echo "$(GREEN)════════════════════════════════════════════════════$(NC)"

# Setup: instalar dependencias
setup:
	@echo "$(YELLOW)→ Configurando entorno de entrenamiento...$(NC)"
	@cd bert-classifier && python3 -m venv .venv
	@cd bert-classifier && .venv/bin/pip install --upgrade pip
	@cd bert-classifier && .venv/bin/pip install torch transformers scikit-learn pandas tqdm jupyter ipykernel
	@cd bert-classifier && .venv/bin/python -m ipykernel install --user --name=cie10-training
	@echo "$(GREEN)✓ Entorno configurado correctamente$(NC)"

# Descargar dataset
dataset:
	@echo "$(YELLOW)→ Descargando dataset CODIESP...$(NC)"
	@cd csv_import_scripts && make collect_codiesp

# Abrir Jupyter Notebook
jupyter:
	@echo "$(YELLOW)→ Abriendo Jupyter Notebook...$(NC)"
	@cd bert-classifier && source .venv/bin/activate && jupyter notebook clasificador_jerarquico_2niveles.ipynb

# Entrenar modelo
train:
	@echo "$(YELLOW)→ Entrenando modelo (esto puede tardar varias horas)...$(NC)"
	@cd bert-classifier && source .venv/bin/activate && jupyter nbconvert --to notebook --execute clasificador_jerarquico_2niveles.ipynb --output clasificador_jerarquico_2niveles_executed.ipynb

# Exportar modelo a ai_engine
export:
	@echo "$(YELLOW)→ Exportando modelo a ai_engine...$(NC)"
	@mkdir -p ../ai_engine/model
	@cp bert-classifier/snapshots/nivel1_capitulos/best_model.pt ../ai_engine/model/chapter_classifier.pt || echo "$(YELLOW)Advertencia: No se encontró modelo Nivel 1$(NC)"
	@cp bert-classifier/snapshots/nivel2_codigos/best_model.pt ../ai_engine/model/code_classifier.pt || echo "$(YELLOW)Advertencia: No se encontró modelo Nivel 2$(NC)"
	@echo "$(GREEN)✓ Modelos exportados a ai_engine/model/$(NC)"

# Limpiar todo
clean:
	@echo "$(YELLOW)→ Limpiando entornos virtuales...$(NC)"
	@cd csv_import_scripts && make clean || true
	@cd bert-classifier && rm -rf .venv __pycache__ .ipynb_checkpoints
	@echo "$(GREEN)✓ Limpieza completada$(NC)"
