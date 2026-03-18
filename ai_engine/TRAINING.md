# CIE-10 AI Engine — Guía de entrenamiento

## Requisitos previos

1. **Docker** y **Docker Compose** instalados
2. **HF_TOKEN** en `.env` — token de HuggingFace con acceso al modelo
3. **Memoria Docker** mínimo 8 GB (Docker Desktop → Settings → Resources → Memory)
4. Datos de CodiESP en `training/csv_import_scripts/`:
   - `codiesp_csvs/codiesp_D_source_train.csv`
   - `codiesp_csvs/codiesp_D_source_validation.csv`
   - `cie10-csvs/cie10-es-diagnoses.csv`

## Comandos de entrenamiento

```bash
# Entrenamiento completo (CPU, modelo por defecto)
make ai-train

# Entrenamiento con GPU NVIDIA
make ai-train-gpu

# Prueba rápida sin token HF (1 época, modelo público, max_length=256)
make ai-train-quick

# Modelo alternativo o parámetros custom
make ai-train MODEL=jhu-clsp/mmBERT-base MAX_LENGTH=1024 BATCH_SIZE=1 GRAD_ACCUM=16
```

## Parámetros del script `train.py`

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `--model_name` | `jhu-clsp/mmBERT-base` | Modelo HuggingFace base |
| `--max_length` | `512` | Longitud máxima de tokens |
| `--epochs` | `20` | Épocas máximas |
| `--batch_size` | `1` | Batch size por paso (CPU: 1 para evitar OOM) |
| `--grad_accum` | `16` | Acumulación de gradientes — batch efectivo = batch_size × grad_accum |
| `--patience` | `5` | Early stopping: épocas sin mejora antes de parar |
| `--threshold` | `0.2` | Umbral sigmoid para predicción positiva |
| `--pos_weight_cap` | `10.0` | Cap máximo de pos_weight por clase (ver sección desbalanceo) |
| `--full_codes` | `False` | Usar código completo (`B86.93D`); por defecto nivel de bloque (`B86`) |
| `--device` | `auto` | `auto`, `cpu`, `cuda`, `mps` |

## Arquitectura del clasificador

El modelo es un **clasificador flat multi-label**: un único encoder + cabeza lineal que
predice simultáneamente todos los códigos CIE-10. No hay jerarquía de capítulos, lo que
evita el error en cascada (si el capítulo falla, todos sus códigos también fallan).

```
texto clínico → tokenizer → encoder (22 capas) → [CLS] → dropout → Linear(hidden, N_códigos) → sigmoid → umbral
```

La función de pérdida es `BCEWithLogitsLoss` (binary cross-entropy por código), con
scheduler coseno y warm-up del 10% de los pasos totales.

## Modo de códigos

El clasificador puede entrenar a dos niveles de granularidad:

| Modo | Ejemplo | Clases aprox. | Ventaja |
|------|---------|---------------|---------|
| **block** (default) | `B86` | ~809 | Más fácil de aprender, targets menos sparse |
| **full** (`--full_codes`) | `B86.93D` | ~1767 | Mayor precisión clínica |

## Selección automática de atención (`attn_implementation`)

Al cargar el encoder se prueban por orden:

1. **`flash_attention_2`** — requiere GPU NVIDIA y el paquete `flash-attn`. Mucho más
   rápido y eficiente en memoria gracias a reordenación de bloques en SRAM.
2. **`sdpa`** — `scaled_dot_product_attention` de PyTorch 2.0+. Funciona en CPU y CUDA,
   usa kernels optimizados automáticamente cuando están disponibles (Flash Attention vía
   PyTorch en CUDA, atención eficiente en CPU).
3. **`eager` (default)** — implementación de referencia, siempre disponible.

El log indica cuál se ha seleccionado: `[model] attn_implementation=sdpa`.

## Mixed precision: bfloat16

El training usa `torch.autocast` con **bfloat16** durante los pasos de forward y backward.

### Por qué bfloat16 y no float32 o float16

| Tipo | Exponente | Mantisa | Riesgo |
|------|-----------|---------|--------|
| float32 | 8 bits | 23 bits | ninguno |
| **bfloat16** | **8 bits** | **7 bits** | mínimo |
| float16 | 5 bits | 10 bits | overflow/underflow frecuente |

bfloat16 conserva el **mismo rango** que float32 (mismo número de bits de exponente),
solo reduce la precisión decimal. En la práctica los gradientes ya son ruidosos por
el SGD estocástico, así que perder 16 bits de mantisa no afecta al resultado final.

**Los pesos del optimizador (Adam) se mantienen siempre en float32**; el autocast solo
afecta a los cómputos del forward/backward, no al almacenamiento de parámetros.

En CPUs modernas con soporte nativo (Apple Silicon M-series, Intel con AMX/AVX-512 BF16)
bfloat16 puede ser ~2× más rápido y usa la mitad de memoria. En CPUs antiguas se emula
y puede ser más lento — en ese caso el beneficio es solo de memoria.

### Qué ocurre en cada device

| Device | dtype usado | Nota |
|--------|-------------|------|
| CUDA con BF16 | bfloat16 | óptimo |
| CUDA sin BF16 | float16 | fallback seguro |
| MPS (Apple GPU) | float16 | ver nota abajo |
| CPU | bfloat16 | nativo en M1/M2/M3 e Intel AMX |

### Apple Silicon — MPS vs Neural Engine

En Mac con chip M, PyTorch puede usar dos aceleradores:

- **MPS (Metal Performance Shaders)** — los cores GPU del chip, accesibles desde PyTorch
  con `device="mps"`. Se selecciona automáticamente con `--device auto` si no hay CUDA.
  Usa float16 (bfloat16 aún no soportado en Metal). Puede ser 3–5× más rápido que CPU
  para matrices grandes.

- **Neural Engine (ANE)** — el acelerador dedicado a inferencia del chip M. **No es
  accesible desde PyTorch**. Solo está disponible vía CoreML / Create ML. Para usarlo
  habría que exportar el modelo a CoreML (`.mlpackage`) tras el entrenamiento.

Con `--device auto` el orden de prioridad es: **CUDA > MPS > CPU**.

## Desbalanceo de clases y pos_weight

CIE-10 es un problema extremadamente desbalanceado: con 809 códigos posibles y una media
de ~10.5 códigos por muestra en el dataset CodiESP (informes clínicos completos), la
tasa de positivos por clase es ~2.1%. Sin corrección, `BCEWithLogitsLoss` aprende que
predecir todo como negativo minimiza el loss (hay ~47 negativos por cada positivo),
lo que produce F1=0 a partir de epoch 2-3.

### Solución: pos_weight por clase

Se calcula automáticamente antes de entrenar a partir del dataset real:

```python
pos_weight[i] = min(neg_count[i] / pos_count[i], cap)
```

El dataset CodiESP tiene dos splits:

- **Train** (`codiesp_D_source_train.csv`): ~500 muestras — usado para entrenar y calcular pos_weight
- **Val** (`codiesp_D_source_validation.csv`): ~250 muestras — usado solo para métricas de validación

El `pos_weight` se calcula **únicamente sobre el split de entrenamiento** (no sobre eval), para
evitar data leakage. Con ~500 muestras y 809 códigos, la ratio neg/pos sin cap sería:

- `pos_weight` media = **46.6**, máx = muy superior (códigos que aparecen 1 vez)

El cap evita pesos extremos para códigos rarísimos. Configurable con `--pos_weight_cap`.

### Progreso de experimentos

Cada paso describe qué se cambió, por qué, y qué resultado produjo.

---

#### Paso 1 — Sin pos_weight

**Cambio:** ninguno, configuración de partida sin corrección de desbalanceo.

**Resultado:** el modelo aprende que predecir todo negativo minimiza el loss
(hay ~47 negativos por cada positivo). **F1=0 desde epoch 3.**

**Decisión:** añadir `pos_weight` para forzar al modelo a aprender positivos.

---

#### Paso 2 — pos_weight con cap=50

**Cambio:** se añadió `BCEWithLogitsLoss(pos_weight=...)` con cap=50. También se
bajó el learning rate de 2e-5 a **5e-6** para evitar colapso de gradientes con
pesos tan elevados, y se bajó el threshold de 0.5 a **0.2** porque las
probabilidades tienden a ser bajas con pos_weight alto.

**Por qué cap=50:** primera aproximación conservadora — simplemente limitar los casos
extremos (un código que aparece 1 sola vez tendría pos_weight=499, demasiado).

**Resultado** (19 épocas, MPS local, early stopping epoch 19):

| Epoch | Loss   | P micro | R micro | F1 micro |
|-------|--------|---------|---------|----------|
| 1     | 1.1336 | 0.009   | 0.417   | 0.018    |
| 5     | 1.0950 | 0.009   | 0.405   | 0.018    |
| 6     | 0.9492 | 0.017   | 0.376   | 0.033    |
| 10    | 0.7268 | 0.041   | 0.341   | 0.073    |
| 14    | 0.6448 | 0.044   | 0.348   | 0.078 ← best     |
| 19    | 0.6114 | 0.043   | 0.351   | 0.076    |

El modelo mejoró (F1=0.018 → 0.078) pero la precision nunca supera el 4.4%.
Con pos_weight media ~46.6×, la penalización es tan alta que el modelo aprende
a "predecir todo" para evitar falsos negativos. Recall=35%, Precision=4%.

**Decisión:** reducir el cap para que la penalización sea menos extrema.

---

#### Paso 3 — pos_weight con cap=10 (valor actual por defecto)

**Cambio:** `--pos_weight_cap 10` (añadido como argumento CLI, `make ai-train`
usa este valor por defecto). La media efectiva de pos_weight baja de ~46.6 a ~10.

**Por qué cap=10:** los falsos negativos se penalizan 10× (no 47×), forzando al
modelo a predecir positivos pero con penalización razonable que le permita
discriminar. La mayoría de los 809 códigos tienen ratio real > 10, así que todos
quedan capeados en 10 — la distribución de pesos se hace mucho más uniforme.

**Resultado:** pendiente (lanzar con `make ai-train`).

**Ajuste posterior:** si sigue sobre-prediciendo (P<10%), subir threshold a 0.3-0.4.
Si infra-predice (R<20%), bajar cap a 5 o threshold a 0.1.

Para ajustar el equilibrio precision/recall:

```bash
make ai-train POS_WEIGHT_CAP=5    # más selectivo (mayor precision, menor recall)
make ai-train POS_WEIGHT_CAP=20   # más permisivo (mayor recall, menor precision)
```

## Gradient checkpointing

Activado automáticamente en el encoder. En lugar de guardar todas las activaciones
intermedias durante el forward pass (necesarias para el backward), las recalcula bajo
demanda capa a capa. Reduce el uso de memoria ~3–4× a costa de ~30% más de tiempo de
cómputo por paso. Imprescindible para entrenar modelos de 22+ capas en CPU o GPUs con
poca VRAM.

## Métricas de validación

Tras cada época se calculan precision, recall y F1 en dos promedios:

- **micro**: pondera por número de instancias — refleja el rendimiento global en los
  códigos más frecuentes. Es la métrica principal para early stopping.
- **macro**: media simple entre todos los códigos — refleja el rendimiento en códigos
  raros. Suele ser bastante menor que micro en datasets desbalanceados como CIE-10.

Output por época:
```
  epoch 2/20  loss=0.7134  P=0.312  R=0.198  F1=0.241 (micro)  |  P=0.089  R=0.064  F1=0.071 (macro)  [18m23s/epoch  elapsed 36m47s  ETA 5h31m]
```

## Artefactos generados

Todos se guardan en `ai_engine/model/`:

| Archivo | Descripción |
|---------|-------------|
| `classifier.pt` | Pesos del mejor modelo + mapeos code↔idx |
| `config.json` | Hiperparámetros usados (model_name, max_length, threshold, full_codes) |
| `code_descriptions.json` | Descripciones de los códigos CIE-10 |
| `cie10_chapters.json` | Metadatos de capítulos CIE-10 |
| `training_runs.csv` | Histórico acumulado de todos los runs (append por run) |
| `training_curve_<timestamp>.png` | Gráfica con 3 paneles: loss, P/R/F1-micro por época, F1-micro vs F1-macro |

### Columnas de `training_runs.csv`

`timestamp`, `model_name`, `full_codes`, `max_length`, `epochs_run`, `epochs_max`,
`batch_size`, `grad_accum`, `patience`, `threshold`, `pos_weight_cap`, `train_rows`, `val_rows`,
`num_codes`, `val_p_micro`, `val_r_micro`, `val_f1_micro`, `val_p_macro`,
`val_r_macro`, `val_f1_macro`, `total_seconds`, `avg_epoch_seconds`

## Flujo tras entrenamiento

El modelo se carga automáticamente cuando se levanta el `ai_engine`:

```bash
make cpu-up   # modo mock (sin modelo real)
make up       # con GPU
```

El servicio expone:
- `GET /` — health check + `model_loaded: true/false`
- `POST /predict` — `{"text": "..."}` → tarjetas con códigos CIE-10

## Caché de HuggingFace

El volumen `huggingface_cache` persiste los modelos descargados entre runs para evitar
re-descargas. Montado en `/root/.cache/huggingface` dentro del contenedor.
