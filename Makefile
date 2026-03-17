.PHONY: help build build-base build-backend build-frontend build-ai build-training up down restart logs logs-backend logs-frontend logs-ai logs-db logs-mail clean clean-all dev setup backend-shell backend-migrate backend-rollback backend-seed backend-reset backend-test backend-install backend-format backend-inspect frontend-shell frontend-test frontend-install frontend-format frontend-lint frontend-inspect ai-shell ai-install db-shell db-backup db-reset ps stats prod-build prod-up mailpit training-setup training-dataset training-jupyter training-train training-export training-all training-clean training-docker-cpu training-docker-gpu cpu-build cpu-up cpu-down cpu-dev cpu-logs-ai cpu-ai-shell

# Variables
COMPOSE     = docker compose -f docker-compose.yml -f docker-compose.gpu.yml
COMPOSE_CPU = docker compose -f docker-compose.yml -f docker-compose.cpu.yml
BACKEND = $(COMPOSE) exec backend
FRONTEND = $(COMPOSE) exec frontend
AI = $(COMPOSE) exec ai_engine
DB = $(COMPOSE) exec db

# Colores para output
GREEN = \033[0;32m
YELLOW = \033[1;33m
BLUE = \033[0;34m
NC = \033[0m # No Color

help: ## Mostrar esta ayuda
	@echo "$(GREEN)CIE-10 Medical Classifier - Comandos disponibles:$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

# Comandos de Docker Compose
build-base: ## Construir imagen base ML compartida (CUDA + PyTorch + Transformers)
	@echo "$(GREEN)Construyendo imagen base ML...$(NC)"
	docker build -t cie10-ml-base:latest -f Dockerfile.ml-base .

build: build-base ## Construir todos los contenedores
	@echo "$(GREEN)Construyendo contenedores...$(NC)"
	$(COMPOSE) build

build-backend:## Construir solo backend
	@echo "$(GREEN)Construyendo backend...$(NC)"
	$(COMPOSE) build backend

build-frontend: ## Construir solo frontend
	@echo "$(GREEN)Construyendo frontend...$(NC)"
	$(COMPOSE) build frontend

build-ai: build-base ## Construir solo AI engine
	@echo "$(GREEN)Construyendo AI engine...$(NC)"
	$(COMPOSE) build ai_engine

build-training: build-base ## Construir solo training
	@echo "$(GREEN)Construyendo training...$(NC)"
	$(COMPOSE) build training

up: ## Levantar todos los servicios
	@echo "$(GREEN)Levantando servicios...$(NC)"
	$(COMPOSE) up -d
	@echo "$(GREEN)Servicios levantados:$(NC)"
	@echo "  - Frontend:    http://localhost:3000"
	@echo "  - Backend API: http://localhost:4000"
	@echo "  - AI Engine:   http://localhost:8000"
	@echo "  - Mailpit UI:  http://localhost:8025"
	@echo "  - PostgreSQL:  localhost:5432"

down: ## Detener todos los servicios
	@echo "$(YELLOW)Deteniendo servicios...$(NC)"
	$(COMPOSE) down

restart: ## Reiniciar todos los servicios
	@echo "$(YELLOW)Reiniciando servicios...$(NC)"
	$(COMPOSE) restart

logs: ## Ver logs de todos los servicios
	$(COMPOSE) logs -f

logs-backend: ## Ver logs del backend
	$(COMPOSE) logs -f backend

logs-frontend: ## Ver logs del frontend
	$(COMPOSE) logs -f frontend

logs-ai: ## Ver logs del AI engine
	$(COMPOSE) logs -f ai_engine

logs-db: ## Ver logs de la base de datos
	$(COMPOSE) logs -f db

logs-mail: ## Ver logs de Mailpit
	$(COMPOSE) logs -f mailpit

mailpit: ## Abrir Mailpit en el navegador (fake email inbox)
	@echo "$(GREEN)Abriendo Mailpit en http://localhost:8025$(NC)"
	open http://localhost:8025 2>/dev/null || xdg-open http://localhost:8025 2>/dev/null || echo "Abre manualmente: http://localhost:8025"

clean: ## Limpiar contenedores, volúmenes e imágenes
	@echo "$(YELLOW)Limpiando todo...$(NC)"
	$(COMPOSE) down -v --remove-orphans
	docker system prune -f

clean-all: ## Limpieza profunda (incluye imágenes)
	@echo "$(YELLOW)Limpieza profunda...$(NC)"
	$(COMPOSE) down -v --rmi all --remove-orphans
	docker system prune -af

# Comandos de desarrollo
dev: ## Levantar servicios en modo desarrollo con logs
	@echo "$(GREEN)Iniciando modo desarrollo...$(NC)"
	$(COMPOSE) up

setup: build ## Setup inicial del proyecto
	@echo "$(GREEN)Setup inicial del proyecto...$(NC)"
	$(COMPOSE) up -d db
	@echo "Esperando a PostgreSQL..."
	@sleep 5
	$(COMPOSE) up -d backend
	@echo "Esperando inicialización del backend..."
	@sleep 10
	$(COMPOSE) up -d ai_engine frontend
	@echo "$(GREEN)Setup completado!$(NC)"

# Shells interactivos
backend-shell: ## Abrir shell en el contenedor del backend
	$(BACKEND) sh

frontend-shell: ## Abrir shell en el contenedor del frontend
	$(FRONTEND) sh

ai-shell: ## Abrir shell en el contenedor de IA
	$(AI) sh

db-shell: ## Abrir shell de PostgreSQL
	$(DB) psql -U postgres -d cie10_app

# Comandos de base de datos
backend-migrate: ## Ejecutar migraciones de Ecto
	@echo "$(GREEN)Ejecutando migraciones...$(NC)"
	$(BACKEND) mix ecto.migrate

backend-rollback: ## Rollback última migración
	@echo "$(YELLOW)Rollback de migración...$(NC)"
	$(BACKEND) mix ecto.rollback

backend-seed: ## Poblar base de datos con datos de prueba
	@echo "$(GREEN)Poblando base de datos...$(NC)"
	$(BACKEND) mix run priv/repo/seeds.exs

db-reset: ## Resetear base de datos (drop, create, migrate, seed)
	@echo "$(YELLOW)Reseteando base de datos...$(NC)"
	$(BACKEND) mix ecto.drop
	$(BACKEND) mix ecto.create
	$(BACKEND) mix ecto.migrate

# Testing
backend-test: ## Ejecutar tests del backend
	@echo "$(GREEN)Ejecutando tests...$(NC)"
	$(BACKEND) mix test

frontend-test: ## Ejecutar tests del frontend
	@echo "$(GREEN)Ejecutando tests del frontend...$(NC)"
	$(FRONTEND) npm test

# Comandos útiles
ps: ## Ver estado de los servicios
	$(COMPOSE) ps

stats: ## Ver estadísticas de recursos
	docker stats

backend-inspect: ## Inspeccionar configuración del backend
	$(COMPOSE) config backend

frontend-inspect: ## Inspeccionar configuración del frontend
	$(COMPOSE) config frontend

# Producción
prod-build: ## Build para producción
	@echo "$(GREEN)Building para producción...$(NC)"
	$(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml build

prod-up: ## Levantar en modo producción
	@echo "$(GREEN)Levantando en modo producción...$(NC)"
	$(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml up -d

# Instalación de dependencias
backend-install: ## Instalar dependencias del backend
	$(BACKEND) mix deps.get

frontend-install: ## Instalar dependencias del frontend
	$(FRONTEND) npm install

ai-install: ## Instalar dependencias del AI engine
	$(AI) pip install -r requirements.txt

# Formato y linting
backend-format: ## Formatear código del backend
	$(BACKEND) mix format

frontend-format: ## Formatear código del frontend
	$(FRONTEND) npm run format

frontend-lint: ## Lint del frontend
	$(FRONTEND) npm run lint

# Backup y restore
db-backup: ## Backup de la base de datos
	@echo "$(GREEN)Creando backup...$(NC)"
	docker exec cie10_db pg_dump -U postgres cie10_app > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Backup creado!$(NC)"

# Training y ML con prefijo training-
training-setup: ## Configurar entorno de entrenamiento
	@echo "$(YELLOW)→ Configurando entorno de entrenamiento (Docker)...$(NC)"
	$(COMPOSE) run --rm training bash -c 'cd bert-classifier && python3 -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install torch transformers scikit-learn pandas tqdm jupyter ipykernel && .venv/bin/python -m ipykernel install --user --name=cie10-training'
	@echo "$(GREEN)✓ Entorno configurado correctamente$(NC)"

training-dataset: ## Descargar dataset CODIESP
	@echo "$(YELLOW)→ Descargando dataset CODIESP (Docker)...$(NC)"
	$(COMPOSE) run --rm training bash -c 'cd csv_import_scripts && python3 collect_codiesp_dataset.py'

training-collect-chemicals: ## Descargar tabla de químicos
	@echo "$(YELLOW)→ Descargando tabla de químicos (Docker)...$(NC)"
	$(COMPOSE) run --rm training bash -c 'cd csv_import_scripts && python3 collect_chemicals.py'

training-collect-diagnoses: ## Descargar diagnósticos
	@echo "$(YELLOW)→ Descargando diagnósticos (Docker)...$(NC)"
	$(COMPOSE) run --rm training bash -c 'cd csv_import_scripts && python3 collect_diagnoses.py'

training-collect-procedures: ## Descargar procedimientos
	@echo "$(YELLOW)→ Descargando procedimientos (Docker)...$(NC)"
	$(COMPOSE) run --rm training bash -c 'cd csv_import_scripts && python3 collect_procedures.py'

training-jupyter: ## Abrir Jupyter para entrenar manualmente
	@echo "$(YELLOW)→ Abriendo Jupyter Notebook (Docker)...$(NC)"
	@echo "$(YELLOW)  Jupyter disponible en: http://localhost:8888$(NC)"
	@echo "$(YELLOW)  Abriendo navegador en 3 segundos...$(NC)"
	@echo "$(YELLOW)  CTRL+C para detener$(NC)"
	@(sleep 3 && xdg-open http://localhost:8888 2>/dev/null || true) & \
	$(COMPOSE) run --rm --service-ports training bash -c 'cd bert-classifier && jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --NotebookApp.token="" --NotebookApp.password="" --NotebookApp.disable_check_xsrf=True --NotebookApp.trust_xheaders=True'

training-train: ## Entrenar modelo CIE-10 completo
	@echo "$(YELLOW)→ Entrenando modelo (Docker, esto puede tardar varias horas)...$(NC)"
	$(COMPOSE) run --rm training bash -c 'cd bert-classifier && source .venv/bin/activate && jupyter nbconvert --to notebook --execute clasificador_jerarquico_2niveles.ipynb --output clasificador_jerarquico_2niveles_executed.ipynb'

training-export: ## Exportar modelo entrenado a ai_engine
	@echo "$(YELLOW)→ Exportando modelo a ai_engine (Docker)...$(NC)"
	$(COMPOSE) run --rm training bash -c 'mkdir -p ../ai_engine/model && cp bert-classifier/snapshots/nivel1_capitulos/best_model.pt ../ai_engine/model/chapter_classifier.pt 2>/dev/null || echo "Advertencia: No se encontró modelo Nivel 1" && cp bert-classifier/snapshots/nivel2_codigos/best_model.pt ../ai_engine/model/code_classifier.pt 2>/dev/null || echo "Advertencia: No se encontró modelo Nivel 2"'
	@echo "$(GREEN)✓ Modelos exportados a ai_engine/model/$(NC)"

training-all: ## Pipeline completo: setup + dataset + train + export
	@echo "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@echo "$(BLUE)  Pipeline completo de entrenamiento CIE-10$(NC)"
	@echo "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@echo ""
	$(MAKE) training-setup
	$(MAKE) training-dataset
	$(MAKE) training-train
	$(MAKE) training-export
	@echo "$(GREEN)════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)  ✓ Pipeline completo finalizado$(NC)"
	@echo "$(GREEN)  Modelo entrenado y exportado a ai_engine/$(NC)"
	@echo "$(GREEN)════════════════════════════════════════════════════$(NC)"

training-clean: ## Limpiar entornos de entrenamiento
	@echo "$(YELLOW)→ Limpiando entorno de entrenamiento (Docker)...$(NC)"
	$(COMPOSE) run --rm training bash -c 'cd csv_import_scripts && make clean || true; cd ../bert-classifier && rm -rf .venv __pycache__ .ipynb_checkpoints'
	@echo "$(GREEN)✓ Limpieza completada$(NC)"

training-docker-cpu: ## Ejecutar entorno Docker training (CPU)
	@echo "$(YELLOW)→ Ejecutando entorno Docker training (CPU)...$(NC)"
	docker run -it --rm -v $$(pwd):/workspace -w /workspace/training cie10-training

training-docker-gpu: ## Ejecutar entorno Docker training (GPU)
	@echo "$(YELLOW)→ Ejecutando entorno Docker training (GPU, si disponible)...$(NC)"
	docker run --gpus all -it --rm -v $$(pwd):/workspace -w /workspace/training cie10-training

# Modo CPU (desarrollo sin GPU)
cpu-build: ## Construir AI engine CPU/mock (sin CUDA, imagen ligera)
	@echo "$(GREEN)Construyendo AI engine CPU...$(NC)"
	$(COMPOSE_CPU) build ai_engine

cpu-up: ## Levantar servicios en modo CPU (sin GPU)
	@echo "$(GREEN)Levantando servicios en modo CPU...$(NC)"
	$(COMPOSE_CPU) up -d db backend frontend ai_engine
	@echo "$(GREEN)Servicios levantados (modo CPU):$(NC)"
	@echo "  - Frontend:    http://localhost:3000"
	@echo "  - Backend API: http://localhost:4000"
	@echo "  - AI Engine:   http://localhost:8000 (CPU mock)"
	@echo "  - Mailpit UI:  http://localhost:8025"
	@echo "  - PostgreSQL:  localhost:5432"

cpu-down: ## Detener servicios del modo CPU
	@echo "$(YELLOW)Deteniendo servicios CPU...$(NC)"
	$(COMPOSE_CPU) down

cpu-dev: ## Levantar modo CPU con logs en consola
	@echo "$(GREEN)Iniciando modo desarrollo CPU...$(NC)"
	$(COMPOSE_CPU) up db backend frontend ai_engine

cpu-logs-ai: ## Ver logs del AI engine CPU
	$(COMPOSE_CPU) logs -f ai_engine

cpu-ai-shell: ## Abrir shell en el AI engine CPU
	$(COMPOSE_CPU) exec ai_engine sh

# Default target
.DEFAULT_GOAL := help
