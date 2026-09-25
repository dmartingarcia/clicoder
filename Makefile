.PHONY: e2e-tests ai-bench-predict ai-eval-candidatos ai-eval-candidatos-fusion ai-motores ai-bench-explain ai-error-analysis ai-coverage backend-coverage frontend-coverage coverage ai-augment ai-baseline-dict ai-combine ai-eval-test ai-format ai-install ai-lint ai-train ai-train-gpu audit audit-backend audit-js audit-python backend-dialyzer backend-format backend-install backend-lint backend-migrate backend-reset backend-rollback backend-seed backend-test build build-ai build-backend build-base build-frontend build-training clean clean-all cpu-build cpu-down cpu-up db-backup db-reset deploy down frontend-format frontend-install frontend-lint frontend-test help logs mock-build mock-down mock-up model-download model-upload network-create setup shell start-monitoring start-monitoring-dev start-proxy start-tunnel stop-monitoring stop-proxy stop-tunnel traefik-passwd tfg-clean tfg-lint tfg-pdf training-clean training-collect-chemicals training-collect-diagnoses training-collect-procedures training-dataset training-jupyter-cpu training-jupyter-gpu training-setup up

-include .env
export

# Autodetecta GPU; GPU=0 fuerza CPU.
GPU ?= $(shell command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1 && echo 1)

# Variables: compose stacks
COMPOSE            = docker compose -f docker-compose.yml -f docker-compose.gpu.yml
COMPOSE_CPU        = docker compose -f docker-compose.yml -f docker-compose.cpu.yml
COMPOSE_MOCK       = docker compose -f docker-compose.yml -f docker-compose.mock.yml

# Candidatos a promocion, en formato nombre:checkpoint:umbrales (ver ai-eval-candidatos)
CANDIDATOS = \
  produccion:classifier.pt:thresholds.json \
  c102909:classifier_20260915T102909Z_f1=0.5028_map=0.5566.pt:thresholds_20260915T102909Z.json \
  zlpr-map:zlpr-map.pt:zlpr-map.thresholds.json
COMPOSE_MONITORING     = docker compose -f docker-compose.monitoring.yml
COMPOSE_MONITORING_DEV = docker compose -f docker-compose.monitoring.yml -f docker-compose.monitoring.dev.yml
COMPOSE_PROXY      = docker compose -f docker-compose-proxy.yml
COMPOSE_TUNNEL     = docker compose -f docker-compose-proxy.yml --profile tunnel
COMPOSE_DEV        = docker compose -f docker-compose.yml -f docker-compose.cpu.yml -f docker-compose.dev.yml
COMPOSE_DEV_GPU    = docker compose -f docker-compose.yml -f docker-compose.gpu.yml -f docker-compose.dev.yml
COMPOSE_PROD       = docker compose -f docker-compose.yml -f docker-compose.cpu.yml -f docker-compose.prod.yml
COMPOSE_PROD_GPU   = docker compose -f docker-compose.yml -f docker-compose.gpu.yml -f docker-compose.prod.yml
NETWORK            = clicoder
BACKEND = $(COMPOSE) exec backend
FRONTEND = $(COMPOSE) exec frontend
AI = $(COMPOSE) exec ai_engine
DB = $(COMPOSE) exec db

# Variables: modelo Hugging Face
HF_REPO      = dmartingarcia/cie10-rigoberta-classifier
MODEL_DIR    = ai_engine/model
BEST_PT      = classifier_20260530T030233Z_f1=0.4945.pt
BEST_THR     = thresholds_20260530T030233Z.json
AI_MODEL_DIR = /app/model

# Variables: TFG
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
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-30s$(NC) %s\n", $$1, $$2}'
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

ai-augment-paraphrase: ## Paráfrasis con Gemma 3 4B IT (GPU). Vars: N_PER_NOTE=1 TEMPERATURE=0.7 DRY_RUN=1 RESUME=1
	@echo "$(BLUE)Paráfrasis de notas clínicas con Gemma 3 4B IT...$(NC)"
	$(COMPOSE) run --rm \
		-e HUGGING_FACE_HUB_TOKEN=$${HUGGING_FACE_HUB_TOKEN} \
		ai_engine python augment_paraphrase.py \
		--input_file  /data/codiesp_csvs/codiesp_D_source_train.csv \
		--output_file /data/codiesp_csvs/codiesp_D_source_train_augmented_paraphrase.csv \
		$(if $(N_PER_NOTE),--n_per_note $(N_PER_NOTE),) \
		$(if $(TEMPERATURE),--temperature $(TEMPERATURE),) \
		$(if $(DRY_RUN),--dry_run,) \
		$(if $(RESUME),--resume,)
	@echo "$(GREEN)Datos guardados en /data/codiesp_csvs/codiesp_D_source_train_augmented_paraphrase.csv$(NC)"

ai-baseline-dict: ## Calcular y guardar diccionario CIE-10 en CPU (clinical+corpus+combined -> model/baseline_dict.json)
	@echo "$(BLUE)Calculando diccionario CIE-10 (CPU)...$(NC)"
	$(COMPOSE_CPU) run --rm ai_engine python baseline_dict.py \
		--train_file        /data/codiesp_csvs/codiesp_D_source_train.csv \
		--val_file          /data/codiesp_csvs/codiesp_D_source_validation.csv \
		--test_file         /data/codiesp_csvs/codiesp_D_source_test.csv \
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
		$(if $(CORPUS_MIN_PRECISION),--corpus_min_precision $(CORPUS_MIN_PRECISION),) \
		$(if $(NO_ABBREVS),--no_expand_abbrevs,)

ai-baseline-dict-gpu: ## Calcular y guardar diccionario CIE-10 en GPU (clinical+corpus+combined -> model/baseline_dict.json)
	@echo "$(BLUE)Calculando diccionario CIE-10 (GPU)...$(NC)"
	$(COMPOSE) run --rm ai_engine python baseline_dict.py \
		--train_file        /data/codiesp_csvs/codiesp_D_source_train.csv \
		--val_file          /data/codiesp_csvs/codiesp_D_source_validation.csv \
		--test_file         /data/codiesp_csvs/codiesp_D_source_test.csv \
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
		$(if $(CORPUS_MIN_PRECISION),--corpus_min_precision $(CORPUS_MIN_PRECISION),) \
		$(if $(NO_ABBREVS),--no_expand_abbrevs,)

ai-combine: ## Combina los CSV aumentados (EN+DE+FR) en un único fichero de entrenamiento
	@echo "$(BLUE)Combinando CSV aumentados...$(NC)"
	$(COMPOSE) run --rm ai_engine python combine_augmented.py
	@echo "$(GREEN)Combinado en /data/codiesp_csvs/codiesp_D_source_train_augmented_all.csv$(NC)"

ai-format: ## Formatear código del AI engine (ruff format)
	$(AI) pip install -q ruff
	$(AI) python -m ruff format .

ai-install: ## Instalar dependencias del AI engine
	$(AI) pip install -r requirements.txt

ai-test: ## Tests del AI engine (pytest). Uso: make ai-test [ARGS="-k chapter -v"]
	$(COMPOSE_CPU) run --rm --no-deps ai_engine sh -c "pip install -q -r requirements-dev.txt && python -m pytest tests/ -q -p no:cacheprovider $(ARGS)"

ai-lint: ## Lint del AI engine y su mock, igual que la CI (ruff check + format check)
# --isolated en ai_engine_mock: ruff resuelve config por CWD, no por la ruta objetivo, y sin
# esto heredaba el line-length=100 de ai_engine/pyproject.toml.
	$(COMPOSE) run --rm -v $(PWD)/ai_engine_mock:/ai_engine_mock ai_engine sh -c "\
		pip install -q ruff && \
		python -m ruff check --cache-dir /tmp/ruff . && \
		python -m ruff check --isolated --cache-dir /tmp/ruff /ai_engine_mock && \
		python -m ruff format --check --cache-dir /tmp/ruff . && \
		python -m ruff format --check --isolated --cache-dir /tmp/ruff /ai_engine_mock"

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
		$(if $(SELECT_METRIC),--select_metric $(SELECT_METRIC),) \
		$(if $(RANK_LOSS_WEIGHT),--rank_loss_weight $(RANK_LOSS_WEIGHT),) \
		$(if $(RDROP_ALPHA),--rdrop_alpha $(RDROP_ALPHA),) \
		$(if $(EMA_DECAY),--ema_decay $(EMA_DECAY),) \
		$(if $(SEED),--seed $(SEED),) \
		$(if $(PUSH_TO_HUB),--push_to_hub,) \
		$(if $(DISTILL_FROM),--distill_from $(DISTILL_FROM),) \
		$(if $(DISTILL_ALPHA),--distill_alpha $(DISTILL_ALPHA),) \
		$(if $(HF_REPO_OVERRIDE),--hf_repo $(HF_REPO_OVERRIDE),) \
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
		$(if $(SELECT_METRIC),--select_metric $(SELECT_METRIC),) \
		$(if $(RANK_LOSS_WEIGHT),--rank_loss_weight $(RANK_LOSS_WEIGHT),) \
		$(if $(RDROP_ALPHA),--rdrop_alpha $(RDROP_ALPHA),) \
		$(if $(EMA_DECAY),--ema_decay $(EMA_DECAY),) \
		$(if $(SEED),--seed $(SEED),) \
		$(if $(PUSH_TO_HUB),--push_to_hub,) \
		$(if $(DISTILL_FROM),--distill_from $(DISTILL_FROM),) \
		$(if $(DISTILL_ALPHA),--distill_alpha $(DISTILL_ALPHA),) \
		$(if $(HF_REPO_OVERRIDE),--hf_repo $(HF_REPO_OVERRIDE),) \
		--device cuda
	@echo "$(GREEN)Modelo guardado en ai_engine/model/$(NC)"
	@echo "$(BLUE)Generando gráfico comparativo de runs...$(NC)"
	$(COMPOSE) run --rm ai_engine python plot_runs.py
	@echo "$(GREEN)Gráfico guardado en ai_engine/model/all_trainings_graph.png$(NC)"

ai-bench-explain: ## Coste y fidelidad de los metodos de atribucion. Uso: make ai-bench-explain [DEVICE=cuda]
	@echo "$(BLUE)Midiendo los metodos de explicabilidad ($(or $(DEVICE),cpu))...$(NC)"
# La imagen del motor lleva torch de CPU, asi que para medir en GPU hay que usar la de
# entrenamiento montando el codigo del motor y los CSV del corpus. La variante de diccionario
# se omite ahi porque necesita spaCy, que esa imagen no trae, y ademas no usa el acelerador.
ifeq ($(DEVICE),cuda)
	$(COMPOSE) run --rm --no-deps \
		-v $(PWD)/ai_engine:/app -v $(PWD)/training/csv_import_scripts:/data \
		-w /app --entrypoint python3 training bench_explain.py --device cuda
else
	$(COMPOSE_CPU) run --rm --no-deps ai_engine python bench_explain.py --device cpu
endif

ai-bench-predict: ## Latencia de proponer codigos. Uso: make ai-bench-predict [DEVICE=cuda] [N=30]
	@echo "$(BLUE)Midiendo la latencia de prediccion ($(or $(DEVICE),cpu))...$(NC)"
ifeq ($(DEVICE),cuda)
	$(COMPOSE) run --rm --no-deps \
		-v $(PWD)/ai_engine:/app -v $(PWD)/training/csv_import_scripts:/data \
		-w /app --entrypoint python3 training bench_predict.py --device cuda --n $(or $(N),30)
else
	$(COMPOSE_CPU) run --rm --no-deps ai_engine python bench_predict.py --device cpu --n $(or $(N),30)
endif

ai-error-analysis: ## Clasificar los errores del modelo sobre test (especificidad vs comprensión)
	@echo "$(BLUE)Analizando los errores del modelo...$(NC)"
	$(if $(filter 1,$(GPU)),$(COMPOSE),$(COMPOSE_CPU)) run --rm ai_engine python error_analysis.py \
		--test_file $(or $(TEST_FILE),/data/codiesp_csvs/codiesp_D_source_test.csv) \
		--threshold $(or $(THRESHOLD),0.3)

ai-eval-candidatos: ## Evaluar en test los candidatos a promocion y sacar la tabla comparativa
	@echo "$(BLUE)Evaluando candidatos en test (GPU)...$(NC)"
# Como ai-bench-explain: la imagen del motor lleva torch de CPU, asi que para GPU se usa la de
# entrenamiento montando el codigo del motor y los CSV del corpus. Cada checkpoint se evalua con
# sus propios umbrales y sin tocar config.json, que seguiria apuntando al modelo que sirve.
	@for c in $(CANDIDATOS); do \
		nombre=$${c%%:*}; resto=$${c#*:}; pt=$${resto%%:*}; thr=$${resto##*:}; \
		echo "$(BLUE)--- $$nombre ---$(NC)"; \
		$(COMPOSE) run --rm --no-deps \
			-v $(PWD)/ai_engine:/app -v $(PWD)/training/csv_import_scripts:/data \
			-w /app --entrypoint python3 training eval_test.py --device cuda \
			--model_file "$$pt" --thresholds_file "$$thr" \
			--out "model/eval_cand_$$nombre.json" || exit 1; \
	done
	@python3 ai_engine/tabla_candidatos.py

ai-eval-candidatos-fusion: ## MAP de los candidatos en modo fusionado con el diccionario
	@echo "$(BLUE)Midiendo la fusion con diccionario de cada candidato (GPU)...$(NC)"
# El titular del trabajo es el modo fusionado, y su beta se ajusta por modelo, de modo que la
# comparativa sin diccionario no basta para decidir una promocion. La ablacion 'solo_diccionario'
# de rerank_map es la que corresponde al motor 'fused' que sirve el sistema.
	@for c in $(CANDIDATOS); do \
		nombre=$${c%%:*}; resto=$${c#*:}; pt=$${resto%%:*}; \
		echo "$(BLUE)--- $$nombre ---$(NC)"; \
		$(COMPOSE) run --rm --no-deps \
			-v $(PWD)/ai_engine:/app -v $(PWD)/training/csv_import_scripts:/data \
			-w /app --entrypoint python3 training rerank_map.py --device cuda \
			--ckpt "/app/model/$$pt" --label "$$nombre" \
			--dict_patterns /app/model/baseline_dict.json \
			--betas 0,1,2,4,6,8,12 \
			--out "/app/model/rerank_cand_$$nombre.json" || exit 1; \
	done
	@python3 ai_engine/tabla_candidatos.py

ai-motores: ## Comparativa de los cuatro motores y barrido de beta de la fusion (GPU)
	@echo "$(BLUE)Comparando motores y barriendo beta...$(NC)"
# De aqui salen las cifras titulares del modo fusionado. Necesita spaCy (diccionario) y CUDA,
# que es lo que trae la imagen de entrenamiento.
	$(COMPOSE) run --rm --no-deps \
		-v $(PWD)/ai_engine:/app -v $(PWD)/training/csv_import_scripts:/data \
		-w /app --entrypoint python3 training motores_eval.py --device $(or $(DEVICE),cuda)
	@echo "$(GREEN)Resultados en ai_engine/model/comparativa_motores.json y fusion_sweep.json$(NC)"

ai-eval-test: ## Evaluar sobre el test de CodiEsp. Uso: make ai-eval-test [GPU=1] [DEVICE=cpu|cuda] [THRESHOLD=0.3]
	@echo "$(BLUE)Evaluando modelo sobre el conjunto de test...$(NC)"
	$(if $(filter 1,$(GPU)),$(COMPOSE),$(COMPOSE_CPU)) run --rm ai_engine python eval_test.py \
		--test_file $(or $(TEST_FILE),/data/codiesp_csvs/codiesp_D_source_test.csv) \
		--device $(or $(DEVICE),auto) \
		--threshold $(or $(THRESHOLD),0.3)
	@echo "$(GREEN)Resultados en ai_engine/model/eval_test.json$(NC)"

ai-tfg-figures: ## Generar las figuras de datos del TFG (lee model/eval_test.json). Uso: make ai-tfg-figures [GPU=1]
	@echo "$(BLUE)Generando figuras del TFG...$(NC)"
	$(if $(filter 1,$(GPU)),$(COMPOSE),$(COMPOSE_CPU)) run --rm ai_engine python plot_tfg_figures.py
	@echo "$(BLUE)Copiando a tfg/figs/...$(NC)"
	cp ai_engine/model/tfg_*.png tfg/figs/
	@echo "$(GREEN)Figuras actualizadas en tfg/figs/$(NC)"

audit: audit-python audit-js audit-backend ## Auditar CVEs en todas las dependencias

audit-backend: ## Auditar dependencias Elixir retiradas/vulnerables (mix hex.audit)
	@echo "$(BLUE)Auditando dependencias Elixir...$(NC)"
	$(COMPOSE_CPU) run --rm --no-deps backend mix hex.audit

audit-js: ## Auditar CVEs en dependencias JS/Node (npm audit)
	@echo "$(BLUE)Auditando dependencias JS...$(NC)"
# El stage por defecto es el de producción, que no instala devDependencies ni trae el lockfile
# completo, así que "npm audit" falla con ENOLOCK. Necesita el stage de desarrollo.
	$(COMPOSE_DEV) run --rm --no-deps frontend npm audit

audit-python: ## Auditar CVEs en dependencias Python (pip-audit)
	@echo "$(BLUE)Auditando dependencias Python...$(NC)"
	$(COMPOSE_CPU) run --rm --no-deps \
		-v $(CURDIR)/ai_engine:/audit:ro \
		ai_engine sh -c 'pip install -q pip-audit && python -m pip_audit -r /audit/requirements.txt -r /audit/requirements-dev.txt'

backend-dialyzer: ## Análisis estático de tipos del backend (Dialyzer)
	$(BACKEND) mix deps.get
	$(BACKEND) mix dialyzer --format dialyxir

backend-format: ## Formatear código del backend
	$(BACKEND) mix format

backend-install: ## Instalar dependencias del backend
	$(COMPOSE_CPU) run --rm backend sh -c "mix deps.get && mix deps.compile && mix compile"

backend-lint: ## Lint del backend, igual que la CI (format + compile estricto + credo + dialyzer)
	$(BACKEND) mix deps.get
	$(BACKEND) mix format --check-formatted
	$(BACKEND) mix compile --warnings-as-errors
	$(BACKEND) mix credo --strict
	$(BACKEND) mix dialyzer --format dialyxir

backend-migrate: ## Ejecutar migraciones de Ecto
	$(COMPOSE_CPU) up -d db
	$(COMPOSE_CPU) run --rm backend mix ecto.migrate

backend-rollback: ## Rollback última migración
	$(COMPOSE_CPU) up -d db
	$(COMPOSE_CPU) run --rm backend mix ecto.rollback

backend-seed: backend-install ## Primera vez: create + migrate + eventstore + seeds + CIE-10
	$(COMPOSE_CPU) up -d db
	$(COMPOSE_CPU) run --rm backend mix ecto.create
	$(COMPOSE_CPU) run --rm backend mix ecto.migrate
	$(COMPOSE_CPU) run --rm backend mix event_store.create
	$(COMPOSE_CPU) run --rm backend mix event_store.init
	$(COMPOSE_CPU) run --rm backend mix run priv/repo/seeds.exs
	$(COMPOSE_CPU) run --rm backend mix cie10.import
	@echo "$(GREEN)Admin: $(SEED_ADMIN_EMAIL) / $(SEED_ADMIN_PASSWORD)$(NC)"

backend-coverage: ## Cobertura de pruebas del backend (excoveralls). Uso: make backend-coverage [ARGS="--detail"]
	@echo "$(BLUE)Midiendo cobertura del backend...$(NC)"
	$(COMPOSE_CPU) run --rm --no-deps -e MIX_ENV=test backend mix coveralls $(ARGS)

frontend-coverage: ## Cobertura de pruebas del frontend (vitest + v8)
	@echo "$(BLUE)Midiendo cobertura del frontend...$(NC)"
	docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm --no-deps frontend npx vitest run --coverage

ai-coverage: ## Cobertura de pruebas del motor de IA (pytest-cov)
	@echo "$(BLUE)Midiendo cobertura del motor de IA...$(NC)"
# Se miden los módulos que se despliegan. Los guiones de entrenamiento, evaluación y figuras
# se ejecutan a mano una vez y se verifican contra los artefactos que producen, así que
# contarlos solo diluiría la cifra sin decir nada del servicio.
	$(COMPOSE_CPU) run --rm --no-deps ai_engine sh -c "pip install -q -r requirements-dev.txt pytest-cov && cd /app && python -m pytest tests/ -q -p no:cacheprovider --cov=main --cov=classifier --cov=baseline_dict --cov=summarizer --cov=rerank_map --cov=compare_runs --cov-report=term --cov-config=/dev/null"

coverage: backend-coverage ai-coverage frontend-coverage ## Cobertura de los tres proyectos

backend-test: ## Ejecutar tests del backend
	@echo "$(GREEN)Preparando BBDDs de test...$(NC)"
	$(COMPOSE) exec -e MIX_ENV=test backend mix ecto.create --quiet
	$(COMPOSE) exec -e MIX_ENV=test backend mix ecto.migrate --quiet
	$(COMPOSE) exec -e MIX_ENV=test backend mix event_store.drop --quiet
	$(COMPOSE) exec -e MIX_ENV=test backend mix event_store.create --quiet
	$(COMPOSE) exec -e MIX_ENV=test backend mix event_store.init --quiet
	@echo "$(GREEN)Ejecutando tests...$(NC)"
	$(COMPOSE) exec -e MIX_ENV=test backend mix test

build: build-base ## Construir todos los contenedores. GPU=1 para modo GPU
	@echo "$(GREEN)Construyendo contenedores...$(NC)"
	$(if $(filter 1,$(GPU)),$(COMPOSE),$(COMPOSE_CPU)) build

build-ai: ## Construir solo AI engine. GPU=1 para modo GPU
	@echo "$(GREEN)Construyendo AI engine...$(NC)"
	$(if $(filter 1,$(GPU)),$(MAKE) build-base,)
	$(if $(filter 1,$(GPU)),$(COMPOSE),$(COMPOSE_CPU)) build ai_engine

build-backend: ## Construir solo backend
	@echo "$(GREEN)Construyendo backend...$(NC)"
	$(COMPOSE) build backend

build-base: ## Construir imagen base ML compartida (CUDA + PyTorch + Transformers)
	@echo "$(GREEN)Construyendo imagen base ML...$(NC)"
	docker build -t cie10-ml-base:latest -f docker/Dockerfile.ml-base ./docker

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

cpu-up: frontend-install network-create ## Levantar servicios en modo CPU (sin GPU)
	@echo "$(GREEN)Levantando servicios en modo CPU...$(NC)"
	$(COMPOSE_DEV) up -d db backend frontend ai_engine
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

# Las dos bases de datos, no solo la de la aplicacion: el registro de eventos es el historial
# inmutable de decisiones y es lo unico que no se puede reconstruir si se pierde.
db-backup: ## Backup de la aplicacion y del registro de eventos
	@echo "$(GREEN)Creando backup...$(NC)"
	$(COMPOSE) exec -T db pg_dump -U postgres cie10_app > backup_app_$(shell date +%Y%m%d_%H%M%S).sql
	$(COMPOSE) exec -T db pg_dump -U postgres cie10_eventstore > backup_eventstore_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Backup creado!$(NC)"

db-reset: ## Reset completo: drop + backend-seed
	$(COMPOSE_CPU) up -d db
	$(COMPOSE_CPU) run --rm backend mix ecto.drop
	$(MAKE) backend-seed

down: ## Detener todos los servicios. GPU=1 para modo GPU
	@echo "$(YELLOW)Deteniendo servicios...$(NC)"
	$(if $(filter 1,$(GPU)),$(COMPOSE),$(COMPOSE_CPU)) down
	$(COMPOSE_MONITORING) down
	$(COMPOSE_PROXY) down

frontend-format: ## Formatear código del frontend
	$(COMPOSE_CPU) run --rm --no-deps frontend npm format

frontend-install: ## Instalar dependencias del frontend
	$(COMPOSE_DEV) run --rm frontend sh -c "npm install && chown -R $$(id -u):$$(id -g) /app/package-lock.json /app/node_modules /app/.npm-cache 2>/dev/null || true"

frontend-lint: ## Lint del frontend (usa volúmenes dev para leer ficheros locales)
	$(COMPOSE_DEV) run --rm --no-deps frontend npm run lint

frontend-test: ## Ejecutar tests del frontend
	@echo "$(GREEN)Ejecutando tests del frontend...$(NC)"
# El stage por defecto es el de producción, que no instala devDependencies y por tanto no
# tiene vitest. Los tests necesitan el stage de desarrollo, que sí las trae.
	docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm --no-deps frontend npm test

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

mock-up: frontend-install network-create ## Levantar servicios en modo mock (sin GPU, sin modelo real)
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

model-list: ## Listar los modelos publicados y sus métricas
	@python3 -c "import json; d=json.load(open('$(MODEL_DIR)/models.json')); \
	print('repo:', d['repo']); \
	print('  (métricas comparables entre sí: misma pasada de evaluación)'); \
	[print(f\"  {k:12} MAP={v['comparables']['map_test']:.4f}  F1={v['comparables']['f1_micro_test']:.4f}  con diccionario MAP={v['comparables']['map_test_con_diccionario']:.4f}  {v['descripcion']}\") for k,v in d['modelos'].items()]; \
	print(); print(d['nota_fusion'])"

model-upload: ## Subir un modelo a HF con nombre propio. Uso: make model-upload NAME=zlpr-map PT=<fichero.pt> THR=<fichero.json>
	@test -n "$(NAME)" || (echo "$(RED)Falta NAME=<nombre del modelo en el catálogo>$(NC)"; exit 1)
	@test -n "$(PT)"   || (echo "$(RED)Falta PT=<ruta del checkpoint>$(NC)"; exit 1)
	@test -n "$(THR)"  || (echo "$(RED)Falta THR=<ruta de los umbrales>$(NC)"; exit 1)
	@echo "$(BLUE)Subiendo '$(NAME)' a HF: $(HF_REPO)$(NC)"
# Se sube con el nombre del catálogo, no sobre classifier.pt: así conviven varias versiones
# en el mismo repositorio y subir una nueva no sustituye a la que está en producción.
	$(COMPOSE_CPU) run --rm --no-deps ai_engine sh -c '\
		HF_HUB_DISABLE_XET=1 HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf upload $(HF_REPO) $(AI_MODEL_DIR)/$(PT)  $(NAME).pt && \
		HF_HUB_DISABLE_XET=1 HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf upload $(HF_REPO) $(AI_MODEL_DIR)/$(THR) $(NAME).thresholds.json'
	@echo "$(GREEN)Subido como $(NAME).pt en https://huggingface.co/$(HF_REPO)$(NC)"

model-upload-shared: ## Subir los artefactos comunes a todos los modelos (descripciones y diccionario)
	@echo "$(BLUE)Subiendo artefactos compartidos a HF: $(HF_REPO)$(NC)"
	$(COMPOSE_CPU) run --rm --no-deps ai_engine sh -c '\
		HF_HUB_DISABLE_XET=1 HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf upload $(HF_REPO) $(AI_MODEL_DIR)/code_descriptions.json code_descriptions.json && \
		HF_HUB_DISABLE_XET=1 HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf upload $(HF_REPO) $(AI_MODEL_DIR)/baseline_dict.json     baseline_dict.json && \
		HF_HUB_DISABLE_XET=1 HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf upload $(HF_REPO) $(AI_MODEL_DIR)/models.json            models.json && \
		HF_HUB_DISABLE_XET=1 HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf upload $(HF_REPO) $(AI_MODEL_DIR)/config.json            config.json'
	@echo "$(GREEN)Artefactos compartidos subidos$(NC)"

model-download: ## Descargar un modelo. Uso: make model-download [NAME=zlpr-map] (sin NAME baja el de producción)
	@echo "$(BLUE)Descargando desde HF: $(HF_REPO)$(NC)"
# Los artefactos compartidos se bajan siempre; el checkpoint, solo el pedido.
	$(COMPOSE_CPU) run --rm --no-deps ai_engine sh -c '\
		HF_HUB_DISABLE_XET=1 HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf download $(HF_REPO) code_descriptions.json --local-dir $(AI_MODEL_DIR) && \
		HF_HUB_DISABLE_XET=1 HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf download $(HF_REPO) baseline_dict.json     --local-dir $(AI_MODEL_DIR) && \
		HF_HUB_DISABLE_XET=1 HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf download $(HF_REPO) models.json            --local-dir $(AI_MODEL_DIR) && \
		HF_HUB_DISABLE_XET=1 HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf download $(HF_REPO) config.json            --local-dir $(AI_MODEL_DIR) || true'
	$(if $(NAME),\
		$(COMPOSE_CPU) run --rm --no-deps ai_engine sh -c '\
			HF_HUB_DISABLE_XET=1 HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf download $(HF_REPO) $(NAME).pt               --local-dir $(AI_MODEL_DIR) && \
			HF_HUB_DISABLE_XET=1 HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf download $(HF_REPO) $(NAME).thresholds.json  --local-dir $(AI_MODEL_DIR)',\
		$(COMPOSE_CPU) run --rm --no-deps ai_engine sh -c '\
			HF_HUB_DISABLE_XET=1 HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf download $(HF_REPO) classifier.pt   --local-dir $(AI_MODEL_DIR) && \
			HF_HUB_DISABLE_XET=1 HF_TOKEN=$$HUGGING_FACE_HUB_TOKEN hf download $(HF_REPO) thresholds.json --local-dir $(AI_MODEL_DIR)')
	@echo "$(GREEN)Descargado en $(MODEL_DIR)/$(NC)"

model-use: ## Activar un modelo ya descargado. Uso: make model-use NAME=zlpr-map
	@test -n "$(NAME)" || (echo "$(RED)Falta NAME=<nombre del modelo>$(NC)"; exit 1)
# Reescribe config.json para apuntar al checkpoint elegido y a sus umbrales, incluido el
# umbral de la fusión, que es propio de cada modelo porque vive en el espacio de puntuación.
	@python3 -c "import json,sys; \
	cat=json.load(open('$(MODEL_DIR)/models.json')); \
	m=cat['modelos'].get('$(NAME)') or sys.exit('modelo desconocido: $(NAME)'); \
	cfg=json.load(open('$(MODEL_DIR)/config.json')); \
	cfg.update({'model_file': m['checkpoint'], 'thresholds_file': m['thresholds'], \
	            'threshold': m['umbral'], 'fusion_threshold': m['fusion_threshold']}); \
	json.dump(cfg, open('$(MODEL_DIR)/config.json','w'), indent=2, ensure_ascii=False); \
	print('activo:', m['checkpoint'], '· MAP', (m.get('titulares') or {}).get('map_test', 'sin evaluar'))"
	@echo "$(GREEN)Reinicia el motor para que cargue el modelo nuevo$(NC)"

network-create: ## Crear red Docker compartida entre stacks (proxy, app, monitoring)
	@docker network inspect $(NETWORK) >/dev/null 2>&1 || docker network create $(NETWORK)

setup: network-create ## Setup completo desde cero: down -v + build + seed (sin levantar). Luego usa 'make deploy'
	@[ -f .env ] || cp .env.example .env
	$(COMPOSE_CPU) down -v --remove-orphans
	$(COMPOSE_CPU) --progress=plain build backend frontend ai_engine
	$(MAKE) model-download
	$(MAKE) backend-seed
	@echo "$(GREEN)Setup completado. Usa 'make up' para levantar los servicios. make deploy para producción$(NC)"

start-proxy: network-create ## Arrancar proxy Traefik
	@echo "$(BLUE)Arrancando Traefik...$(NC)"
	$(COMPOSE_PROXY) up -d
	@echo "$(GREEN)Traefik disponible en: https://$${DOMAIN}$(NC)"
	@echo "$(GREEN)Dashboard Traefik:     https://traefik.$${DOMAIN}$(NC)"

stop-proxy: ## Detener proxy Traefik
	@echo "$(YELLOW)Deteniendo Traefik...$(NC)"
	$(COMPOSE_PROXY) down

start-tunnel: network-create ## Arrancar Cloudflare Tunnel (requiere CLOUDFLARE_TUNNEL_TOKEN en .env)
	@[ -n "$${CLOUDFLARE_TUNNEL_TOKEN}" ] || (echo "$(YELLOW)CLOUDFLARE_TUNNEL_TOKEN no definido en .env$(NC)" && exit 1)
	@echo "$(BLUE)Arrancando Cloudflare Tunnel...$(NC)"
	$(COMPOSE_TUNNEL) up -d cloudflared
	@echo "$(GREEN)Tunnel activo. Configurar rutas en: https://dash.cloudflare.com → Zero Trust → Networks → Tunnels$(NC)"
	@echo "$(GREEN)  Apuntar cada ruta a https://cie10_traefik:443 (noTLSVerify: true)$(NC)"

stop-tunnel: ## Detener Cloudflare Tunnel
	@echo "$(YELLOW)Deteniendo Cloudflare Tunnel...$(NC)"
	$(COMPOSE_TUNNEL) stop cloudflared
	$(COMPOSE_TUNNEL) rm -f cloudflared

traefik-passwd: ## Generar hash htpasswd para el dashboard. Vars: USER=admin PASSWORD=changeme
	@echo "$(BLUE)Generando hash htpasswd...$(NC)"
	@hash=$$(docker run --rm httpd:alpine htpasswd -nbm $(or $(USER),admin) $(or $(PASSWORD),changeme)); \
	 echo "$$hash"; \
	 echo ""; \
	 echo "$(YELLOW)Lista para .env (signos dolar escapados para Make):$(NC)"; \
	 echo "$$hash" | sed 's/\$$/$$$$/g'; \
	 echo ""; \
	 echo "$(YELLOW)Copia la segunda linea como TRAEFIK_DASHBOARD_AUTH en .env$(NC)"

start-monitoring: network-create ## Arrancar stack de monitorización (Prometheus + Grafana + Loki + cAdvisor + Node Exporter)
	@echo "$(BLUE)Arrancando monitorización...$(NC)"
	$(COMPOSE_MONITORING) up -d
	@echo "$(GREEN)Grafana:  https://grafana.$${DOMAIN:-localhost}$(NC)"

start-monitoring-dev: network-create ## Arrancar monitorización con puertos expuestos (acceso local sin Traefik)
	@echo "$(BLUE)Arrancando monitorización (dev)...$(NC)"
	$(COMPOSE_MONITORING_DEV) up -d
	@echo "$(GREEN)Grafana:       http://localhost:3030  (admin / $${GRAFANA_PASSWORD:-changeme})$(NC)"
	@echo "$(GREEN)Prometheus:    http://localhost:9090$(NC)"
	@echo "$(GREEN)cAdvisor:      http://localhost:8082$(NC)"
	@echo "$(GREEN)Node Exporter: http://localhost:9100/metrics$(NC)"

stop-monitoring: ## Detener stack de monitorización
	@echo "$(YELLOW)Deteniendo monitorización...$(NC)"
	$(COMPOSE_MONITORING) down

deploy: network-create start-proxy start-monitoring ## Deploy completo. GPU=1 para GPU, TUNNEL=1 para Cloudflare Tunnel
	@echo "$(BLUE)Desplegando CIE-10...$(NC)"
	$(if $(filter 1,$(GPU)),$(COMPOSE_PROD_GPU),$(COMPOSE_PROD)) build frontend backend ai_engine
	$(MAKE) backend-migrate
	$(if $(filter 1,$(GPU)),$(COMPOSE_PROD_GPU),$(COMPOSE_PROD)) up -d db backend frontend ai_engine
	$(if $(filter 1,$(TUNNEL)),$(MAKE) start-tunnel,)
	@echo ""
	@echo "$(GREEN)Deploy completado:$(NC)"
	@echo "  - Frontend:    https://$${DOMAIN:-localhost}"
	@echo "  - Backend API: https://api.$${DOMAIN:-localhost}"
	@echo "  - Grafana:     https://grafana.$${DOMAIN:-localhost}"
	@echo "  - Traefik:     https://traefik.$${DOMAIN:-localhost}"
	@if [ "$(TUNNEL)" = "1" ]; then echo "  - Tunnel:      activo (rutas en Cloudflare dashboard)"; fi

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

tfg-lint: tfg-pdf ## Comprobar que el TFG compila sin errores (usado en CI)

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
	$(COMPOSE_CPU) run --rm training bash -c 'cd csv_import_scripts && make clean; cd ../bert-classifier && rm -rf .venv __pycache__ .ipynb_checkpoints'
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
	@(sleep 3 && xdg-open http://localhost:8888 2>/dev/null) & \
	$(COMPOSE_CPU) run --rm --service-ports training bash -c 'cd bert-classifier && jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --NotebookApp.token="" --NotebookApp.password="" --NotebookApp.disable_check_xsrf=True --NotebookApp.trust_xheaders=True'

training-jupyter-gpu: ## Abrir Jupyter (GPU)
	@echo "$(YELLOW)Abriendo Jupyter Notebook (GPU)...$(NC)"
	@echo "$(YELLOW)  Jupyter disponible en: http://localhost:8888$(NC)"
	@echo "$(YELLOW)  Abriendo navegador en 3 segundos...$(NC)"
	@echo "$(YELLOW)  CTRL+C para detener$(NC)"
	@(sleep 3 && xdg-open http://localhost:8888 2>/dev/null) & \
	$(COMPOSE) run --rm --service-ports training bash -c 'cd bert-classifier && jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --NotebookApp.token="" --NotebookApp.disable_check_xsrf=True --NotebookApp.trust_xheaders=True'

training-setup: ## Configurar entorno de entrenamiento
	@echo "$(YELLOW)Configurando entorno de entrenamiento (Docker)...$(NC)"
	$(COMPOSE_CPU) run --rm training bash -c 'cd bert-classifier && python3 -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install torch transformers scikit-learn pandas tqdm jupyter ipykernel && .venv/bin/python -m ipykernel install --user --name=cie10-training'
	@echo "$(GREEN)Entorno configurado correctamente$(NC)"

up: frontend-install ## Levantar todos los servicios. GPU=1 para modo GPU
	@echo "$(GREEN)Levantando servicios...$(NC)"
	$(if $(filter 1,$(GPU)),$(COMPOSE_DEV_GPU),$(COMPOSE_DEV)) up -d
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

e2e-tests: ## Tests de extremo a extremo con Playwright (requiere la aplicacion levantada)
	@echo "$(GREEN)Tests de extremo a extremo...$(NC)"
	@test -d e2e/.venv || python3 -m venv e2e/.venv
	@e2e/.venv/bin/pip install -q -r e2e/requirements.txt
	@e2e/.venv/bin/playwright install chromium
	cd e2e && .venv/bin/pytest
