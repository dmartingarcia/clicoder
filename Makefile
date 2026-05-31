.PHONY: ai-augment ai-baseline-dict ai-combine ai-format ai-install ai-lint ai-train ai-train-gpu backend-dialyzer backend-format backend-install backend-lint backend-migrate backend-reset backend-rollback backend-seed backend-test build build-ai build-backend build-base build-frontend build-training clean clean-all cpu-build cpu-down cpu-up db-backup db-reset down frontend-format frontend-install frontend-lint frontend-test help logs mock-build mock-down mock-up model-download model-upload setup shell tfg-clean tfg-pdf training-clean training-collect-chemicals training-collect-diagnoses training-collect-procedures training-dataset training-jupyter-cpu training-jupyter-gpu training-setup up

# Variables — compose stacks
COMPOSE      = docker compose -f docker-compose.yml -f docker-compose.gpu.yml
COMPOSE_CPU  = docker compose -f docker-compose.yml -f docker-compose.cpu.yml
COMPOSE_MOCK = docker compose -f docker-compose.yml -f docker-compose.mock.yml
BACKEND = $(COMPOSE) exec backend
FRONTEND = $(COMPOSE) exec frontend
AI = $(COMPOSE) exec ai_engine
DB = $(COMPOSE) exec db

# Variables — modelo Hugging Face
HF_REPO      = dmartingarcia/cie10-rigoberta-classifier
MODEL_DIR    = ai_engine/model
BEST_PT      = classifier_20260530T030233Z_f1=0.4945.pt
BEST_THR     = thresholds_20260530T030233Z.json
AI_MODEL_DIR = /app/model

# Variables — TFG
TFG_DIR   = tfg
TFG_MAIN  = uclmTFGesi
TFG_OUT   = $(TFG_DIR)/build
TFG_IMAGE = texlive/texlive:latest

# Colores para output
GREEN  = \033[0;32m
YELLOW = \033[1;33m
BLUE   = \033[0;34m
NC     = \033[0m # No Color

help: ## Mostrar esta ayuda
	@echo "$(GREEN)CIE-10 Medical Classifier - Comandos disponibles:$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-30s$(NC) %s\n", $$1, $$2}'
	@echo ""

ai-augment: ## Back-translation. Vars: TRANS_BACKEND=azure|nllb PIVOT_LANGS="EN FR" DRY_RUN=1 RESUME=1 ONLY_ROW=N
	@echo "$(BLUE)Aumentando datos con back-translation (backend: $(or $(TRANS_BACKEND),nllb))...$(NC)"
	$(COMPOSE) run --rm \
		-e AZURE_TRANSLATOR_KEY=$${AZURE_TRANSLATOR_KEY} \
		-e AZURE_TRANSLATOR_REGION=$${AZURE_TRANSLATOR_REGION:-global} \
		ai_engine python augment.py \
		--backend     $(or $(TRANS_BACKEND),nllb) \
		--input_file  /data/codiesp_csvs/codiesp_D_source_train.csv \
		--output_file /data/codiesp_csvs/codiesp_D_source_train_augmented.csv \
		--pivot_langs $(or $(PIVOT_LANGS),EN) \
		$(if $(NLLB_MODEL),--nllb_model $(NLLB_MODEL),) \
		$(if $(NLLB_BATCH),--nllb_batch $(NLLB_BATCH),) \
		$(if $(DRY_RUN),--dry_run,) \
		$(if $(RESUME),--resume,) \
		$(if $(ONLY_ROW),--only_row $(ONLY_ROW),)
	@echo "$(GREEN)Datos guardados en /data/codiesp_csvs/codiesp_D_source_train_augmented.csv$(NC)"

ai-baseline-dict: ## Calcular y guardar diccionario CIE-10 (clinical+corpus+combined → model/baseline_dict.json)
	@echo "$(BLUE)Calculando diccionario CIE-10...$(NC)"
	$(COMPOSE_CPU) run --rm ai_engine python baseline_dict.py \
		--train_file        /data/codiesp_csvs/codiesp_D_source_train.csv \
		--val_file          /data/codiesp_csvs/codiesp_D_source_validation.csv \
		--diagnoses_file    /data/cie10-csvs/cie10-es-diagnoses.csv \
		--procedures_file   /data/cie10-csvs/cie10-es-procedures.csv \
		--chemicals_file    /data/cie10-csvs/cie10-es-chemicals.csv \
		--task_x_train      /data/codiesp_csvs/codiesp_X_source_train.csv \
		--task_x_val        /data/codiesp_csvs/codiesp_X_source_validation.csv \
		--sources clinical corpus combined \
		--corpus_selective \
		--only_combined \
		--save_dict         /app/model/baseline_dict.json \
		$(if $(SOURCES),--sources $(SOURCES),) \
		$(if $(MIN_LEN),--min_phrase_len $(MIN_LEN),) \
		$(if $(NO_ABBREVS),--no_expand_abbrevs,)

ai-combine: ## Combina los CSV aumentados (EN+DE+FR) en un único fichero de entrenamiento
	@echo "$(BLUE)Combinando CSV aumentados...$(NC)"
	$(COMPOSE) run --rm ai_engine python combine_augmented.py
	@echo "$(GREEN)Combinado en /data/codiesp_csvs/codiesp_D_source_train_augmented_all.csv$(NC)"

ai-format: ## Formatear código del AI engine (ruff format)
	$(AI) pip install -q ruff
	$(AI) ruff format .

ai-install: ## Instalar dependencias del AI engine
	$(AI) pip install -r requirements.txt

ai-lint: ## Lint del AI engine (ruff check + format check)
	$(AI) pip install -q ruff
	$(AI) ruff check .
	$(AI) ruff format --check .

ai-train: ## Entrenar clasificador CIE-10 en CPU (MODEL=IIC/RigoBERTa-Clinical, requiere HF_TOKEN en .env)
	@echo "$(BLUE)Entrenando clasificador CIE-10 (CPU)$(NC)"
	$(COMPOSE_CPU) run --rm ai_engine python train.py \
		--train_file $(or $(TRAIN_FILE),/data/codiesp_csvs/codiesp_D_source_train.csv) \
		--val_file   /data/codiesp_csvs/codiesp_D_source_validation.csv \
		--cie10_file /data/cie10-csvs/cie10-es-diagnoses.csv \
		--output_dir /app/model \
		--model_name $(or $(MODEL),IIC/RigoBERTa-Clinical) \
		--max_length $(or $(MAX_LENGTH),1024) \
		--batch_size $(or $(BATCH_SIZE),1) \
		--grad_accum $(or $(GRAD_ACCUM),16) \
		--threshold $(or $(THRESHOLD),0.3) \
		--pos_weight_cap $(or $(POS_WEIGHT_CAP),10.0) \
		--lr $(or $(LR),5e-6) \
		--warmup_ratio $(or $(WARMUP_RATIO),0.1) \
		--weight_decay $(or $(WEIGHT_DECAY),0.01) \
		--dropout $(or $(DROPOUT),0.1) \
		--freeze_layers $(or $(FREEZE_LAYERS),0) \
		--epochs $(or $(EPOCHS),20) \
		--patience $(or $(PATIENCE),5) \
		$(if $(SLIDING_WINDOW),--sliding_window,) \
		--chunk_overlap $(or $(CHUNK_OVERLAP),64) \
		$(if $(FULL_CODES),--full_codes,) \
		$(if $(CHAPTERS),--chapters,) \
		$(if $(PRETRAIN_EPOCHS),--pretrain_epochs $(PRETRAIN_EPOCHS),) \
		$(if $(PRETRAIN_TASKX),--pretrain_taskx $(PRETRAIN_TASKX),) \
		$(if $(ASL_GAMMA_NEG),--asl_gamma_neg $(ASL_GAMMA_NEG),) \
		$(if $(ASL_GAMMA_POS),--asl_gamma_pos $(ASL_GAMMA_POS),) \
		$(if $(ASL_CLIP),--asl_clip $(ASL_CLIP),) \
		$(if $(LABEL_SMOOTHING),--label_smoothing $(LABEL_SMOOTHING),) \
		$(if $(LR_SCHEDULE),--lr_schedule $(LR_SCHEDULE),) \
		$(if $(UNFREEZE_EVERY),--unfreeze_every $(UNFREEZE_EVERY),) \
		$(if $(UNFREEZE_LAYERS),--unfreeze_layers $(UNFREEZE_LAYERS),) \
		$(if $(UNFREEZE_LR_RATIO),--unfreeze_lr_ratio $(UNFREEZE_LR_RATIO),) \
		$(if $(LAMBDA_HIER),--lambda_hier $(LAMBDA_HIER),) \
		--device auto
	@echo "$(GREEN)Modelo guardado en ai_engine/model/$(NC)"
	@echo "$(BLUE)Generando gráfico comparativo de runs...$(NC)"
	$(COMPOSE_CPU) run --rm ai_engine python plot_runs.py
	@echo "$(GREEN)Gráfico guardado en ai_engine/model/all_trainings_graph.png$(NC)"

ai-train-gpu: ## Entrenar con GPU explícita (HF_TOKEN en .env)
	@echo "$(BLUE)Entrenando con GPU...$(NC)"
	$(COMPOSE) run --rm ai_engine python train.py \
		--train_file $(or $(TRAIN_FILE),/data/codiesp_csvs/codiesp_D_source_train.csv) \
		--val_file   /data/codiesp_csvs/codiesp_D_source_validation.csv \
		--cie10_file /data/cie10-csvs/cie10-es-diagnoses.csv \
		--output_dir /app/model \
		--model_name $(or $(MODEL),IIC/RigoBERTa-Clinical) \
		--max_length $(or $(MAX_LENGTH),1024) \
		--batch_size $(or $(BATCH_SIZE),4) \
		--grad_accum $(or $(GRAD_ACCUM),4) \
		--threshold $(or $(THRESHOLD),0.3) \
		--pos_weight_cap $(or $(POS_WEIGHT_CAP),10.0) \
		--lr $(or $(LR),5e-6) \
		--warmup_ratio $(or $(WARMUP_RATIO),0.1) \
		--weight_decay $(or $(WEIGHT_DECAY),0.01) \
		--dropout $(or $(DROPOUT),0.1) \
		--freeze_layers $(or $(FREEZE_LAYERS),0) \
		--epochs $(or $(EPOCHS),20) \
		--patience $(or $(PATIENCE),5) \
		$(if $(SLIDING_WINDOW),--sliding_window,) \
		--chunk_overlap $(or $(CHUNK_OVERLAP),64) \
		$(if $(FULL_CODES),--full_codes,) \
		$(if $(CHAPTERS),--chapters,) \
		$(if $(PRETRAIN_EPOCHS),--pretrain_epochs $(PRETRAIN_EPOCHS),) \
		$(if $(PRETRAIN_TASKX),--pretrain_taskx $(PRETRAIN_TASKX),) \
		$(if $(ASL_GAMMA_NEG),--asl_gamma_neg $(ASL_GAMMA_NEG),) \
		$(if $(ASL_GAMMA_POS),--asl_gamma_pos $(ASL_GAMMA_POS),) \
		$(if $(ASL_CLIP),--asl_clip $(ASL_CLIP),) \
		$(if $(LABEL_SMOOTHING),--label_smoothing $(LABEL_SMOOTHING),) \
		$(if $(LR_SCHEDULE),--lr_schedule $(LR_SCHEDULE),) \
		$(if $(UNFREEZE_EVERY),--unfreeze_every $(UNFREEZE_EVERY),) \
		$(if $(UNFREEZE_LAYERS),--unfreeze_layers $(UNFREEZE_LAYERS),) \
		$(if $(UNFREEZE_LR_RATIO),--unfreeze_lr_ratio $(UNFREEZE_LR_RATIO),) \
		$(if $(LAMBDA_HIER),--lambda_hier $(LAMBDA_HIER),) \
		--device cuda
	@echo "$(GREEN)Modelo guardado en ai_engine/model/$(NC)"
	@echo "$(BLUE)Generando gráfico comparativo de runs...$(NC)"
	$(COMPOSE) run --rm ai_engine python plot_runs.py
	@echo "$(GREEN)Gráfico guardado en ai_engine/model/all_trainings_graph.png$(NC)"

backend-dialyzer: ## Análisis estático de tipos del backend (Dialyzer)
	$(BACKEND) mix deps.get
	$(BACKEND) mix dialyzer --format dialyxir

backend-format: ## Formatear código del backend
	$(BACKEND) mix format

backend-install: ## Instalar dependencias del backend
	$(COMPOSE_CPU) run --rm backend mix deps.get

backend-lint: ## Lint del backend (format check + credo)
	$(BACKEND) mix deps.get
	$(BACKEND) mix compile
	$(BACKEND) mix format --check-formatted
	$(BACKEND) mix credo --strict

backend-migrate: ## Ejecutar migraciones de Ecto
	$(COMPOSE_CPU) up -d db
	$(COMPOSE_CPU) run --rm backend mix ecto.migrate

backend-rollback: ## Rollback última migración
	$(COMPOSE_CPU) up -d db
	$(COMPOSE_CPU) run --rm backend mix ecto.rollback

backend-seed: backend-install ## Primera vez: create + migrate + eventstore + seeds + CIE-10
	$(COMPOSE_CPU) up -d db
	$(COMPOSE_CPU) run --rm backend mix ecto.create || true
	$(COMPOSE_CPU) run --rm backend mix ecto.migrate
	$(COMPOSE_CPU) run --rm backend mix event_store.create || true
	$(COMPOSE_CPU) run --rm backend mix event_store.init || true
	$(COMPOSE_CPU) run --rm backend mix run priv/repo/seeds.exs
	$(COMPOSE_CPU) run --rm backend mix cie10.import
	@echo "$(GREEN)Usuario de prueba: admin@test.com / password123$(NC)"

backend-test: ## Ejecutar tests del backend
	@echo "$(GREEN)Preparando BBDDs de test...$(NC)"
	$(COMPOSE) exec -e MIX_ENV=test backend mix ecto.create --quiet || true
	$(COMPOSE) exec -e MIX_ENV=test backend mix ecto.migrate --quiet
	$(COMPOSE) exec -e MIX_ENV=test backend mix event_store.drop --quiet 2>/dev/null || true
	$(COMPOSE) exec -e MIX_ENV=test backend mix event_store.create --quiet 2>/dev/null
	$(COMPOSE) exec -e MIX_ENV=test backend mix event_store.init --quiet 2>/dev/null
	@echo "$(GREEN)Ejecutando tests...$(NC)"
	$(COMPOSE) exec -e MIX_ENV=test backend mix test

build: build-base ## Construir todos los contenedores
	@echo "$(GREEN)Construyendo contenedores...$(NC)"
	$(COMPOSE) build

build-ai: build-base ## Construir solo AI engine. GPU=1 para modo GPU
	@echo "$(GREEN)Construyendo AI engine...$(NC)"
	$(if $(filter 1,$(GPU)),$(COMPOSE),$(COMPOSE_CPU)) build ai_engine

build-backend: ## Construir solo backend
	@echo "$(GREEN)Construyendo backend...$(NC)"
	$(COMPOSE) build backend

build-base: ## Construir imagen base ML compartida (CUDA + PyTorch + Transformers)
	@echo "$(GREEN)Construyendo imagen base ML...$(NC)"
	docker build -t cie10-ml-base:latest -f Dockerfile.ml-base .

build-frontend: ## Construir solo frontend
	@echo "$(GREEN)Construyendo frontend...$(NC)"
	$(COMPOSE) build frontend

build-training: build-base ## Construir solo training
	@echo "$(GREEN)Construyendo training...$(NC)"
	$(COMPOSE) build training

clean: ## Limpiar contenedores, volúmenes e imágenes
	@echo "$(YELLOW)Limpiando todo...$(NC)"
	$(COMPOSE_CPU) down -v --remove-orphans
	docker system prune -f

clean-all: ## Limpieza profunda (incluye imágenes)
	@echo "$(YELLOW)Limpieza profunda...$(NC)"
	$(COMPOSE_CPU) down -v --rmi all --remove-orphans
	docker system prune -af

cpu-build: ## Construir AI engine en modo CPU (sin CUDA)
	@echo "$(GREEN)Construyendo AI engine (CPU)...$(NC)"
	$(COMPOSE_CPU) build ai_engine

cpu-down: ## Detener servicios del modo CPU
	@echo "$(YELLOW)Deteniendo servicios CPU...$(NC)"
	$(COMPOSE_CPU) down

cpu-up: frontend-install ## Levantar servicios en modo CPU (sin GPU)
	@echo "$(GREEN)Levantando servicios en modo CPU...$(NC)"
	$(COMPOSE_CPU) up -d db backend frontend ai_engine
	@echo "$(GREEN)Servicios levantados (modo CPU):$(NC)"
	@echo "  - Frontend:      http://localhost:3000"
	@echo "  - Backend API:   http://localhost:4000"
	@echo "  - Admin:         http://localhost:4000/admin"
	@echo "  - Live Dashboard:http://localhost:4000/dev/dashboard"
	@echo "  - AI Engine:     http://localhost:8000 (CPU)"
	@echo "  - AI Docs:       http://localhost:8000/docs"
	@echo "  - Mailpit UI:    http://localhost:8025"
	@echo "  - Grafana:       http://localhost:3030"
	@echo "  - Prometheus:    http://localhost:9090"
	@echo "  - PostgreSQL:    localhost:5432"

db-backup: ## Backup de la base de datos
	@echo "$(GREEN)Creando backup...$(NC)"
	docker exec cie10_db pg_dump -U postgres cie10_app > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Backup creado!$(NC)"

db-reset: ## Reset completo: drop + backend-seed
	$(COMPOSE_CPU) up -d db
	$(COMPOSE_CPU) run --rm backend mix ecto.drop || true
	$(MAKE) backend-seed

down: ## Detener todos los servicios. GPU=1 para modo GPU
	@echo "$(YELLOW)Deteniendo servicios...$(NC)"
	$(if $(filter 1,$(GPU)),$(COMPOSE),$(COMPOSE_CPU)) down

frontend-format: ## Formatear código del frontend
	$(COMPOSE_CPU) run --rm --no-deps frontend npm format

frontend-install: ## Instalar dependencias del frontend
	$(COMPOSE_CPU) run --rm frontend npm install

frontend-lint: ## Lint del frontend
	$(COMPOSE_CPU) run --rm --no-deps frontend npm run lint

frontend-test: ## Ejecutar tests del frontend
	@echo "$(GREEN)Ejecutando tests del frontend...$(NC)"
	$(COMPOSE_CPU) run --rm --no-deps frontend npm test

logs: ## Ver logs (pregunta por servicio o todos)
	@echo "$(GREEN)Servicios disponibles:$(NC)"
	@echo "  1) todos"
	@echo "  2) backend"
	@echo "  3) frontend"
	@echo "  4) ai_engine"
	@echo "  5) db"
	@echo "  6) mailpit"
	@read -p "Servicio [1]: " c; \
	case $${c:-1} in \
		1|todos)    $(COMPOSE_CPU) logs -f ;; \
		2|backend)  $(COMPOSE_CPU) logs -f backend ;; \
		3|frontend) $(COMPOSE_CPU) logs -f frontend ;; \
		4|ai_engine) $(COMPOSE_CPU) logs -f ai_engine ;; \
		5|db)       $(COMPOSE_CPU) logs -f db ;; \
		6|mailpit)  $(COMPOSE_CPU) logs -f mailpit ;; \
		*) echo "Opción no válida" ;; \
	esac

mock-build: ## Construir AI engine mock
	@echo "$(GREEN)Construyendo AI engine mock...$(NC)"
	$(COMPOSE_MOCK) build ai_engine

mock-down: ## Detener servicios del modo mock
	@echo "$(YELLOW)Deteniendo servicios mock...$(NC)"
	$(COMPOSE_MOCK) down

mock-up: frontend-install ## Levantar servicios en modo mock (sin GPU, sin modelo real)
	@echo "$(GREEN)Levantando servicios en modo mock...$(NC)"
	$(COMPOSE_MOCK) up -d db backend frontend ai_engine
	@echo "$(GREEN)Servicios levantados (modo mock):$(NC)"
	@echo "  - Frontend:      http://localhost:3000"
	@echo "  - Backend API:   http://localhost:4000"
	@echo "  - Admin:         http://localhost:4000/admin"
	@echo "  - Live Dashboard:http://localhost:4000/dev/dashboard"
	@echo "  - AI Engine:     http://localhost:8000 (mock)"
	@echo "  - AI Docs:       http://localhost:8000/docs"
	@echo "  - Mailpit UI:    http://localhost:8025"
	@echo "  - Grafana:       http://localhost:3030"
	@echo "  - Prometheus:    http://localhost:9090"
	@echo "  - PostgreSQL:    localhost:5432"

model-download: ## Descargar modelo desde Hugging Face a ai_engine/model/
	@echo "$(BLUE)Descargando modelo desde HF: $(HF_REPO)$(NC)"
	$(COMPOSE_CPU) run --rm --no-deps ai_engine sh -c '\
		HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf download $(HF_REPO) classifier.pt          --local-dir $(AI_MODEL_DIR) && \
		HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf download $(HF_REPO) thresholds.json        --local-dir $(AI_MODEL_DIR) && \
		HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf download $(HF_REPO) config.json            --local-dir $(AI_MODEL_DIR) && \
		HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf download $(HF_REPO) code_descriptions.json --local-dir $(AI_MODEL_DIR) && \
		HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf download $(HF_REPO) baseline_dict.json     --local-dir $(AI_MODEL_DIR)'
	@echo "$(GREEN)Modelo descargado en $(MODEL_DIR)/$(NC)"

model-upload: ## Subir mejor modelo a Hugging Face (lee HF_TOKEN de .env)
	@echo "$(BLUE)Subiendo modelo a HF: $(HF_REPO)$(NC)"
	cp $(MODEL_DIR)/$(BEST_PT)  $(MODEL_DIR)/classifier.pt
	cp $(MODEL_DIR)/$(BEST_THR) $(MODEL_DIR)/thresholds.json
	$(COMPOSE_CPU) run --rm --no-deps ai_engine sh -c '\
		HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf upload $(HF_REPO) $(AI_MODEL_DIR)/classifier.pt        classifier.pt && \
		HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf upload $(HF_REPO) $(AI_MODEL_DIR)/thresholds.json      thresholds.json && \
		HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf upload $(HF_REPO) $(AI_MODEL_DIR)/config.json          config.json && \
		HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf upload $(HF_REPO) $(AI_MODEL_DIR)/code_descriptions.json code_descriptions.json && \
		HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf upload $(HF_REPO) $(AI_MODEL_DIR)/baseline_dict.json   baseline_dict.json'
	rm -f $(MODEL_DIR)/classifier.pt $(MODEL_DIR)/thresholds.json
	@echo "$(GREEN)Modelo subido: https://huggingface.co/$(HF_REPO)$(NC)"

setup: ## Setup completo desde cero: down -v + build + seed (sin levantar). Luego usa 'make up'
	@[ -f .env ] || cp .env.example .env
	$(COMPOSE_CPU) down -v --remove-orphans
	$(COMPOSE_CPU) build --progress=plain backend
	$(COMPOSE_CPU) build --progress=plain frontend
	$(MAKE) backend-seed
	@[ -f $(MODEL_DIR)/$(BEST_PT) ] || $(MAKE) model-download
	@echo "$(GREEN)Setup completado. Usa 'make up' para levantar los servicios.$(NC)"

shell: ## Abrir shell interactivo (pregunta por contenedor)
	@echo "$(GREEN)Contenedores disponibles:$(NC)"
	@echo "  1) backend"
	@echo "  2) frontend"
	@echo "  3) ai_engine"
	@echo "  4) db"
	@read -p "Contenedor: " c; \
	case $$c in \
		1|backend)    $(COMPOSE_CPU) exec -it backend sh ;; \
		2|frontend)   $(COMPOSE_CPU) exec -it frontend sh ;; \
		3|ai_engine)  $(COMPOSE_CPU) exec -it ai_engine sh ;; \
		4|db)         $(COMPOSE_CPU) exec -it db psql -U postgres -d cie10_app ;; \
		*) echo "Opción no válida" ;; \
	esac

tfg-clean: ## Limpiar artefactos de compilación del TFG
	@echo "$(YELLOW)Limpiando build del TFG...$(NC)"
	@rm -rf $(TFG_OUT)
	@echo "$(GREEN)Limpio$(NC)"

tfg-pdf: ## Compilar memoria TFG a PDF (requiere Docker)
	@echo "$(BLUE)Compilando TFG con pdflatex + bibtex...$(NC)"
	@mkdir -p $(TFG_OUT)
	docker run --rm \
		-v "$$(pwd)/$(TFG_DIR)":/tfg \
		-w /tfg \
		$(TFG_IMAGE) \
		sh -c 'mkdir -p build build/caps build/preambulo build/anexos && \
		       pdflatex -interaction=nonstopmode -output-directory=build $(TFG_MAIN).tex && \
		       cd build && BIBINPUTS=../ bibtex $(TFG_MAIN) && cd .. && \
		       pdflatex -interaction=nonstopmode -output-directory=build $(TFG_MAIN).tex && \
		       pdflatex -interaction=nonstopmode -output-directory=build $(TFG_MAIN).tex'
	@echo "$(GREEN)PDF generado en $(TFG_OUT)/$(TFG_MAIN).pdf$(NC)"

training-clean: ## Limpiar entornos de entrenamiento
	@echo "$(YELLOW)Limpiando entorno de entrenamiento (Docker)...$(NC)"
	$(COMPOSE_CPU) run --rm training bash -c 'cd csv_import_scripts && make clean || true; cd ../bert-classifier && rm -rf .venv __pycache__ .ipynb_checkpoints'
	@echo "$(GREEN)Limpieza completada$(NC)"

training-collect-chemicals: ## Descargar tabla de químicos
	@echo "$(YELLOW)Descargando tabla de químicos (Docker)...$(NC)"
	$(COMPOSE_CPU) run --rm training bash -c 'cd csv_import_scripts && python3 collect_chemicals.py'

training-collect-diagnoses: ## Descargar diagnósticos
	@echo "$(YELLOW)Descargando diagnósticos (Docker)...$(NC)"
	$(COMPOSE_CPU) run --rm training bash -c 'cd csv_import_scripts && python3 collect_diagnoses.py'

training-collect-procedures: ## Descargar procedimientos
	@echo "$(YELLOW)Descargando procedimientos (Docker)...$(NC)"
	$(COMPOSE_CPU) run --rm training bash -c 'cd csv_import_scripts && python3 collect_procedures.py'

training-dataset: ## Descargar dataset CODIESP
	@echo "$(YELLOW)Descargando dataset CODIESP (Docker)...$(NC)"
	$(COMPOSE_CPU) run --rm training bash -c 'cd csv_import_scripts && python3 collect_codiesp_dataset.py'

training-jupyter-cpu: ## Abrir Jupyter (CPU)
	@echo "$(YELLOW)Abriendo Jupyter Notebook (CPU)...$(NC)"
	@echo "$(YELLOW)  Jupyter disponible en: http://localhost:8888$(NC)"
	@echo "$(YELLOW)  Abriendo navegador en 3 segundos...$(NC)"
	@echo "$(YELLOW)  CTRL+C para detener$(NC)"
	@(sleep 3 && xdg-open http://localhost:8888 2>/dev/null || true) & \
	$(COMPOSE_CPU) run --rm --service-ports training bash -c 'cd bert-classifier && jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --NotebookApp.token="" --NotebookApp.password="" --NotebookApp.disable_check_xsrf=True --NotebookApp.trust_xheaders=True'

training-jupyter-gpu: ## Abrir Jupyter (GPU)
	@echo "$(YELLOW)Abriendo Jupyter Notebook (GPU)...$(NC)"
	@echo "$(YELLOW)  Jupyter disponible en: http://localhost:8888$(NC)"
	@echo "$(YELLOW)  Abriendo navegador en 3 segundos...$(NC)"
	@echo "$(YELLOW)  CTRL+C para detener$(NC)"
	@(sleep 3 && xdg-open http://localhost:8888 2>/dev/null || true) & \
	$(COMPOSE) run --rm --service-ports training bash -c 'cd bert-classifier && jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --NotebookApp.token="" --NotebookApp.password="" --NotebookApp.disable_check_xsrf=True --NotebookApp.trust_xheaders=True'

training-setup: ## Configurar entorno de entrenamiento
	@echo "$(YELLOW)Configurando entorno de entrenamiento (Docker)...$(NC)"
	$(COMPOSE_CPU) run --rm training bash -c 'cd bert-classifier && python3 -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install torch transformers scikit-learn pandas tqdm jupyter ipykernel && .venv/bin/python -m ipykernel install --user --name=cie10-training'
	@echo "$(GREEN)Entorno configurado correctamente$(NC)"

up: frontend-install ## Levantar todos los servicios. GPU=1 para modo GPU
	@echo "$(GREEN)Levantando servicios...$(NC)"
	$(if $(filter 1,$(GPU)),$(COMPOSE),$(COMPOSE_CPU)) up -d
	@echo "$(GREEN)Servicios levantados:$(NC)"
	@echo "  - Frontend:      http://localhost:3000"
	@echo "  - Backend API:   http://localhost:4000"
	@echo "  - Admin:         http://localhost:4000/admin"
	@echo "  - Live Dashboard:http://localhost:4000/dev/dashboard"
	@echo "  - AI Engine:     http://localhost:8000"
	@echo "  - AI Docs:       http://localhost:8000/docs"
	@echo "  - Mailpit UI:    http://localhost:8025"
	@echo "  - Grafana:       http://localhost:3030"
	@echo "  - Prometheus:    http://localhost:9090"
	@echo "  - PostgreSQL:    localhost:5432"

.DEFAULT_GOAL := help
