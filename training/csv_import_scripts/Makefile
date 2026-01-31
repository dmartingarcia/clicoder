.PHONY: help venv collect_chemicals collect_diagnoses collect_procedures collect_codiesp all clean

# Define el entorno virtual
VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

# Colores para la ayuda
GREEN = \033[0;32m
NC = \033[0m

# Meta por defecto
help:
	@echo "$(GREEN)Comandos disponibles:$(NC)"
	@echo "  $(GREEN)make venv$(NC)              - Crea un entorno virtual e instala dependencias"
	@echo "  $(GREEN)make collect_chemicals$(NC) - Ejecuta collect_chemicals.py"
	@echo "  $(GREEN)make collect_diagnoses$(NC) - Ejecuta collect_diagnoses.py"
	@echo "  $(GREEN)make collect_procedures$(NC) - Ejecuta collect_procedures.py"
	@echo "  $(GREEN)make collect_codiesp$(NC)   - Ejecuta collect_codiesp_dataset.py"
	@echo "  $(GREEN)make all$(NC)               - Ejecuta todos los scripts en secuencia"
	@echo "  $(GREEN)make clean$(NC)             - Elimina el entorno virtual"

# Crear entorno virtual e instalar dependencias
$(VENV)/bin/activate: requirements.txt
	@echo "$(GREEN)Creando entorno virtual e instalando dependencias...$(NC)"
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(PIP) install -U pip
	@$(PIP) install -r requirements.txt
	@touch $(VENV)/bin/activate

venv: $(VENV)/bin/activate

# Scripts individuales
collect_chemicals: venv
	@echo "$(GREEN)Ejecutando collect_chemicals.py...$(NC)"
	@$(PYTHON) collect_chemicals.py

collect_diagnoses: venv
	@echo "$(GREEN)Ejecutando collect_diagnoses.py...$(NC)"
	@$(PYTHON) collect_diagnoses.py

collect_procedures: venv
	@echo "$(GREEN)Ejecutando collect_procedures.py...$(NC)"
	@$(PYTHON) collect_procedures.py

collect_codiesp: venv
	@echo "$(GREEN)Ejecutando collect_codiesp_dataset.py...$(NC)"
	@$(PYTHON) collect_codiesp_dataset.py

# Ejecutar todos los scripts en secuencia
all: collect_diagnoses collect_procedures collect_codiesp collect_chemicals
	@echo "$(GREEN)¡Todos los scripts ejecutados correctamente!$(NC)"

# Limpiar entorno virtual
clean:
	@echo "$(GREEN)Eliminando entorno virtual...$(NC)"
	@rm -rf $(VENV)
	@echo "$(GREEN)Entorno virtual eliminado.$(NC)"
