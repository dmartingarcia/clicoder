.PHONY: help build up down restart logs clean dev setup test backend-shell frontend-shell db-shell ai-shell migrate seed

# Variables
COMPOSE = docker compose
BACKEND = $(COMPOSE) exec backend
FRONTEND = $(COMPOSE) exec frontend
AI = $(COMPOSE) exec ai_engine
DB = $(COMPOSE) exec db

# Colores para output
GREEN = \033[0;32m
YELLOW = \033[1;33m
NC = \033[0m # No Color

help: ## Mostrar esta ayuda
	@echo "$(GREEN)CIE-10 Medical Classifier - Comandos disponibles:$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

# Comandos de Docker Compose
build: ## Construir todos los contenedores
	@echo "$(GREEN)Construyendo contenedores...$(NC)"
	$(COMPOSE) build

up: ## Levantar todos los servicios
	@echo "$(GREEN)Levantando servicios...$(NC)"
	$(COMPOSE) up -d
	@echo "$(GREEN)Servicios levantados:$(NC)"
	@echo "  - Frontend: http://localhost:3000"
	@echo "  - Backend API: http://localhost:4000"
	@echo "  - AI Engine: http://localhost:8000"
	@echo "  - PostgreSQL: localhost:5432"

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
migrate: ## Ejecutar migraciones de Ecto
	@echo "$(GREEN)Ejecutando migraciones...$(NC)"
	$(BACKEND) mix ecto.migrate

rollback: ## Rollback última migración
	@echo "$(YELLOW)Rollback de migración...$(NC)"
	$(BACKEND) mix ecto.rollback

seed: ## Poblar base de datos con datos de prueba
	@echo "$(GREEN)Poblando base de datos...$(NC)"
	$(BACKEND) mix run priv/repo/seeds.exs

db-reset: ## Resetear base de datos (drop, create, migrate, seed)
	@echo "$(YELLOW)Reseteando base de datos...$(NC)"
	$(BACKEND) mix ecto.drop
	$(BACKEND) mix ecto.create
	$(BACKEND) mix ecto.migrate
	$(BACKEND) mix event_store.drop
	$(BACKEND) mix event_store.create
	$(BACKEND) mix event_store.init

# Testing
test: ## Ejecutar tests del backend
	@echo "$(GREEN)Ejecutando tests...$(NC)"
	$(BACKEND) mix test

test-frontend: ## Ejecutar tests del frontend
	@echo "$(GREEN)Ejecutando tests del frontend...$(NC)"
	$(FRONTEND) npm test

# Comandos útiles
ps: ## Ver estado de los servicios
	$(COMPOSE) ps

stats: ## Ver estadísticas de recursos
	docker stats

inspect-backend: ## Inspeccionar configuración del backend
	$(COMPOSE) config backend

inspect-frontend: ## Inspeccionar configuración del frontend
	$(COMPOSE) config frontend

# Producción
prod-build: ## Build para producción
	@echo "$(GREEN)Building para producción...$(NC)"
	$(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml build

prod-up: ## Levantar en modo producción
	@echo "$(GREEN)Levantando en modo producción...$(NC)"
	$(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml up -d

# Instalación de dependencias
install-backend: ## Instalar dependencias del backend
	$(BACKEND) mix deps.get

install-frontend: ## Instalar dependencias del frontend
	$(FRONTEND) npm install

install-ai: ## Instalar dependencias del AI engine
	$(AI) pip install -r requirements.txt

# Formato y linting
format-backend: ## Formatear código del backend
	$(BACKEND) mix format

format-frontend: ## Formatear código del frontend
	$(FRONTEND) npm run format

lint-frontend: ## Lint del frontend
	$(FRONTEND) npm run lint

# Backup y restore
backup-db: ## Backup de la base de datos
	@echo "$(GREEN)Creando backup...$(NC)"
	docker exec cie10_db pg_dump -U postgres cie10_app > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Backup creado!$(NC)"

restore-db: ## Restore de la base de datos (especificar FILE=backup.sql)
	@echo "$(YELLOW)Restaurando desde $(FILE)...$(NC)"
	@if [ -z "$(FILE)" ]; then echo "Error: Especifica FILE=backup.sql"; exit 1; fi
	cat $(FILE) | docker exec -i cie10_db psql -U postgres -d cie10_app
	@echo "$(GREEN)Restore completado!$(NC)"

# Training y ML
train-setup: ## Configurar entorno de entrenamiento
	@echo "$(GREEN)Configurando entorno de entrenamiento...$(NC)"
	cd training && make setup

train-dataset: ## Descargar dataset CODIESP
	@echo "$(GREEN)Descargando dataset CODIESP...$(NC)"
	cd training && make dataset

train-jupyter: ## Abrir Jupyter para entrenar manualmente
	@echo "$(GREEN)Abriendo Jupyter Notebook...$(NC)"
	cd training && make jupyter

train-model: ## Entrenar modelo CIE-10 completo
	@echo "$(GREEN)Entrenando modelo CIE-10...$(NC)"
	@echo "$(YELLOW)ADVERTENCIA: Esto puede tardar varias horas$(NC)"
	cd training && make train

train-export: ## Exportar modelo entrenado a ai_engine
	@echo "$(GREEN)Exportando modelo a ai_engine...$(NC)"
	cd training && make export
	@echo "$(GREEN)Reconstruyendo contenedor ai_engine...$(NC)"
	$(COMPOSE) build ai_engine
	$(COMPOSE) up -d ai_engine

train-all: ## Pipeline completo: setup + entrenar + exportar + rebuild
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)  Pipeline completo de entrenamiento$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	cd training && make all
	@echo "$(GREEN)Reconstruyendo contenedor ai_engine...$(NC)"
	$(COMPOSE) build ai_engine
	$(COMPOSE) up -d ai_engine
	@echo "$(GREEN)✓ Pipeline completado y modelo desplegado$(NC)"

train-clean: ## Limpiar entornos de entrenamiento
	cd training && make clean

# Default target
.DEFAULT_GOAL := help
