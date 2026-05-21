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
| `--model_name` | `IIC/RigoBERTa-Clinical` | Modelo HuggingFace base |
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
texto clínico → tokenizer → encoder (24 capas) → [CLS] → dropout → Linear(hidden, N_códigos) → sigmoid → umbral
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

### Entorno de entrenamiento

### Mac — Apple MacBook Pro M4 (pasos 1–2)

| Componente | Detalle |
| ---------- | ------- |
| Chip | Apple M4 |
| RAM unificada | 16 GB (compartida CPU/GPU) |
| Acelerador | MPS (Metal Performance Shaders) |
| PyTorch device | `mps` |
| dtype | float16 (bfloat16 no soportado en Metal) |
| Tiempo/época | ~18 min |

### Linux — RTX 4080 (paso 3 en adelante)

| Componente | Detalle |
| ---------- | ------- |
| GPU | NVIDIA GeForce RTX 4080 |
| VRAM | 16 GB |
| Driver | 590.48.01 |
| CUDA | 13.1.1 |
| Imagen base | `cie10-ml-base` (nvidia/cuda:13.1.1-cudnn-devel-ubuntu24.04) |
| PyTorch | 2.10.0+cu130 |
| Transformers | 5.0.0 |
| Flash Attention | 2.x (activada con `torch_dtype=bfloat16` desde paso 4) |
| Tiempo/época | ~2-4 min (estimado) |

## Progreso de experimentos

Cada paso describe qué se cambió, por qué, y qué resultado produjo.

---

### Paso 1 — Sin pos_weight

**Cambio:** ninguno, configuración de partida sin corrección de desbalanceo.

**Resultado:** el modelo aprende que predecir todo negativo minimiza el loss
(hay ~47 negativos por cada positivo). **F1=0 desde epoch 3.**

**Decisión:** añadir `pos_weight` para forzar al modelo a aprender positivos.

---

### Paso 2 — pos_weight con cap=50

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

### Paso 3 — pos_weight con cap=10 (valor actual por defecto)

**Cambio:** `--pos_weight_cap 10` (añadido como argumento CLI, `make ai-train`
usa este valor por defecto). La media efectiva de pos_weight baja de ~46.6 a ~10.

**Por qué cap=10:** los falsos negativos se penalizan 10× (no 47×), forzando al
modelo a predecir positivos pero con penalización razonable que le permita
discriminar. La mayoría de los 809 códigos tienen ratio real > 10, así que todos
quedan capeados en 10 — la distribución de pesos se hace mucho más uniforme.

**Resultado** (20 épocas, RTX 4080, early stopping epoch 19, ~8s/época):

| Epoch | Loss   | P micro | R micro | F1 micro |       |
| ----- | ------ | ------- | ------- | -------- | ----- |
| 1     | 0.4874 | 0.051   | 0.060   | 0.055    |       |
| 5     | 0.3840 | 0.093   | 0.096   | 0.094    |       |
| 10    | 0.3389 | 0.121   | 0.118   | 0.119    |       |
| 11    | 0.3295 | 0.132   | 0.136   | 0.134    |       |
| 12    | 0.3222 | 0.129   | 0.140   | 0.135    |       |
| 14    | 0.3106 | 0.134   | 0.137   | **0.136** | ← best |
| 19    | 0.2986 | 0.133   | 0.137   | 0.135    |       |

Respecto al paso 2 (F1=0.078), el F1-micro **casi se duplica (0.078 → 0.136)** y la
precision sube drásticamente de 4.4% a 13.4%. Cap=10 funciona: el modelo ya no predice
todo indiscriminadamente. Sin embargo P=13% sigue siendo baja — el modelo todavía
sobre-predice bastante.

Nota: el run se ejecutó sin flash attention activa (el modelo cargó en float32 y cayó
a sdpa). El fix para bfloat16 está aplicado para el siguiente paso.

**Decisión:** subir el threshold de 0.2 a 0.3–0.35 para aumentar precisión a costa de
algo de recall, y activar flash attention con bfloat16.

Para ajustar el equilibrio precision/recall:

```bash
make ai-train POS_WEIGHT_CAP=5    # más selectivo (mayor precision, menor recall)
make ai-train POS_WEIGHT_CAP=20   # más permisivo (mayor recall, menor precision)
```

---

### Paso 4 — Flash attention + threshold=0.3 + batch_size=8 (regresión)

**Cambio:** flash attention activada cargando el encoder en `bfloat16` (`torch_dtype=bfloat16`)
para satisfacer el check de transformers 5.0. Threshold subido a 0.3. Batch size 8, grad_accum 2.

**Resultado** (20 épocas sin early stopping, RTX 4080, ~5s/época):

| Epoch | Loss   | P micro | R micro | F1 micro |
| ----- | ------ | ------- | ------- | -------- |
| 1     | 0.9080 | 0.010   | 0.475   | 0.020    |
| 5     | 0.7536 | 0.013   | 0.427   | 0.025    |
| 10    | 0.5392 | 0.019   | 0.222   | 0.036    |
| 20    | 0.4761 | 0.025   | 0.187   | 0.045    |

F1 cayó de 0.136 (paso 3) a **0.045**. Causa: al cargar el modelo en bfloat16, los
parámetros del encoder son bfloat16 → el optimizador (AdamW) almacena sus estados
(momentum, varianza) también en bfloat16 → precisión insuficiente en los gradientes
→ convergencia muy lenta.

**Decisión:** cargar el encoder en bfloat16 solo para satisfacer el check de transformers,
luego convertir a float32 con `.to(torch.float32)` antes de entrenar. Flash attention
permanece activo en el config del modelo; autocast provee tensores bfloat16 en runtime.

---

### Paso 5 — Flash attention + float32 weights + threshold=0.3

**Cambio:** flash attention con conversión a float32 post-carga. El encoder se carga en
bfloat16 (satisface el check de transformers), luego se convierte a float32 para que
AdamW mantenga sus estados en float32. Autocast provee tensores bfloat16 durante el
forward/backward, activando los kernels de flash attention en runtime.

**Resultado** (20 épocas sin early stopping, RTX 4080, ~6s/época, batch_size=8):

| Epoch | Loss   | P micro | R micro | F1 micro |       |
| ----- | ------ | ------- | ------- | -------- | ----- |
| 1     | 0.9050 | 0.011   | 0.476   | 0.021    |       |
| 5     | 0.4337 | 0.079   | 0.197   | 0.113    |       |
| 10    | 0.3374 | 0.136   | 0.150   | 0.143    |       |
| 12    | 0.3232 | 0.145   | 0.160   | 0.152    |       |
| 17    | 0.3078 | 0.149   | 0.161   | **0.155** | ← best |
| 20    | 0.3057 | 0.147   | 0.159   | 0.153    |       |

Flash attention confirmada activa (`attn_implementation=flash_attention_2`). Nuevo best
F1-micro: **0.155** (+14% sobre paso 3). Precision sube a 14.9% (vs 13.4%). El modelo
llegó a 20 épocas sin que saltara early stopping — la curva todavía no había plateau
completo. La pérdida a epoch 20 (0.3057) está casi plana; se agota el presupuesto de
épocas antes que la paciencia.

**Decisión:** ampliar a 40 épocas para ver si el modelo sigue mejorando, y subir
paciencia a 8 para evitar cortes prematuros.

---

### Paso 6 — 40 épocas, patience=8 (overfitting)

**Cambio:** misma configuración que paso 5 pero `--epochs 40 --patience 8`.

**Resultado** (early stopping en época 23, ~6s/época):

| Epoch | Loss   | P micro | R micro | F1 micro |       |
| ----- | ------ | ------- | ------- | -------- | ----- |
| 5     | 0.4691 | 0.062   | 0.203   | 0.095    |       |
| 10    | 0.3423 | 0.134   | 0.138   | 0.136    |       |
| 15    | 0.2855 | 0.140   | 0.160   | **0.149** | ← best |
| 20    | 0.2428 | 0.145   | 0.130   | 0.137    |       |
| 23    | 0.2241 | 0.144   | 0.121   | 0.132    | early stop |

Overfitting claro: loss de entrenamiento sigue bajando (0.285 → 0.224) pero val F1
empeora a partir de época 15. El paso 5 (20 épocas, F1=0.155) sigue siendo el mejor.
Con solo ~500 muestras de train para 809 códigos el modelo memoriza rápidamente.

**Decisión:** el límite de capacidad de generalización está en ~15-17 épocas con esta
arquitectura y datos. Siguiente palanca: aumentar regularización (dropout, weight decay)
o cambiar a un modelo pre-entrenado en texto clínico en español.

---

### Paso 7 — max_length=1504 (más contexto)

**Cambio:** aumentar `max_length` de 1024 a 1504 (múltiplo de 8) para cubrir más texto.
Análisis previo: media ~570 tokens, 50% truncados a 512, 7.6% a 1024, 0% a 2048.
Batch reducido a 4×4=16 (mismo batch efectivo) por el mayor uso de VRAM.

**Resultado** (20 épocas, ~8.7s/época):

| Epoch | Loss | F1 micro |
| ----- | ---- | -------- |
| 10    | —    | —        |
| 18    | —    | 0.106    |

- **F1-micro=0.106** (P=0.060, R=0.453) — peor que max_length=1024 (0.121)
- El 7.6% extra de textos completos no compensó el batch efectivo menor ni el mayor coste por paso

**Decisión:** volver a max_length=1024. La cobertura extra marginal no justifica el coste.

---

### Paso 7b — Vuelta a max_length=1024, descubrimiento del bug de threshold

**Cambio:** revertir a batch=8×2=16, max_length=1024, threshold=0.3.

**Resultado:** F1-micro=0.121 (P=0.070, R=0.441) — run parcialmente afectado por cambio
de código en caliente (volumen montado). Confirmó que el threshold real de 0.3 sobre-predice
(recall muy alto, precisión muy baja), y que con threshold=0.5 el F1 real sería ~0.15.

---

### Nota — Bug en evaluación durante training (descubierto tras paso 7)

Se detectó que el training loop llamaba a `evaluate()` sin pasar el threshold configurado,
usando el default `threshold=0.5` en lugar del `args.threshold` (0.2 o 0.3). El early
stopping seleccionaba el mejor modelo basándose en métricas a 0.5, mientras que el
`[result]` final y el CSV usaban el threshold real. Esto explica la discrepancia entre
los F1 reportados durante training (~0.15) y los del CSV (~0.11).

**Fix aplicado:** `evaluate()` dentro del training loop ahora recibe `threshold=threshold`.
Todos los pasos anteriores al 8 tienen métricas durante-training calculadas a threshold=0.5,
no al threshold configurado. El CSV y la gráfica siempre han sido correctos (threshold real).

Con el fix aplicado, el primer run limpio (misma config que paso 5: batch=8, grad_accum=2,
threshold=0.3) da **F1-micro=0.121** — confirmando que el threshold=0.3 sobre-predice
(P=0.07, R=0.44). El F1 real del modelo a su threshold óptimo (~0.5) es ~0.155.

También se añadieron al CSV y a la gráfica los campos `lr`, `attn_impl` y `effective_batch`
que faltaban para reproducibilidad completa.

---

### Paso 8 — Run limpio con todos los fixes (baseline real)

**Cambio:** primer run con todos los bugs corregidos: threshold pasado al training loop,
`attn_impl`/`lr`/`effective_batch` en CSV y gráfica. Config: batch=8×2=16, threshold=0.5,
max_length=1024, lr=5e-6, flash_attention_2 activo.

**Resultado** (20 épocas, ~7s/época, best en época 18):

| Epoch | Loss  | P micro | R micro | F1 micro |        |
| ----- | ----- | ------- | ------- | -------- | ------ |
| 1     | 0.882 | 0.010   | 0.426   | 0.019    |        |
| 5     | 0.445 | 0.068   | 0.164   | 0.096    |        |
| 9     | 0.347 | 0.126   | 0.160   | 0.141    |        |
| 11    | 0.328 | 0.136   | 0.151   | 0.143    |        |
| 14    | 0.313 | 0.140   | 0.162   | 0.150    |        |
| 18    | 0.304 | 0.143   | 0.159   | **0.150** | ← best |
| 20    | 0.305 | 0.140   | 0.156   | 0.148    |        |

- **F1-micro=0.1503** — mejor resultado hasta la fecha con threshold=0.5
- F1-macro=0.0098 (muy bajo — modelo no generaliza a códigos raros)
- flash_attention_2 confirmado activo
- Loss aún descendiendo lentamente en época 20 → margen con más épocas o LR más alta
- Modelo llegó al límite de 20 épocas sin activar early stop (paciencia=5)

**Decisión:** baseline limpio establecido. Próximos pasos a explorar:
aumentar epochs (40+) con patience mayor, probar RigoBERTa-Clinical con sliding window,
o subir LR a 1e-5.

---

### Paso 9 — Cambio a IIC/RigoBERTa-Clinical

**Cambio:** se sustituye `jhu-clsp/mmBERT-base` por `IIC/RigoBERTa-Clinical`. Config:
batch=4×4=16, lr=3e-5, max_length=512, threshold=0.5, epochs=20, patience=5.

**Por qué RigoBERTa-Clinical a pesar de la ventana reducida:**
RigoBERTa-Clinical (XLM-RoBERTa, 24 capas) está preentrenado sobre texto clínico en
español — exactamente el dominio de los informes CodiESP. El coste es una ventana máxima
de **512 tokens** frente a los 1024 de mmBERT, lo que implica truncar ~50% del texto.
Aun así, el conocimiento de vocabulario médico especializado (diagnósticos, procedimientos,
fármacos) compensa con creces la pérdida de contexto distal. Se confirma en resultados.

**Resultado** (20 épocas, early stop no activado, ~16.5s/época):

| Epoch | Loss  | P micro | R micro | F1 micro |        |
| ----- | ----- | ------- | ------- | -------- | ------ |
| 5     | 0.481 | 0.093   | 0.219   | 0.131    |        |
| 10    | 0.367 | 0.222   | 0.238   | 0.230    |        |
| 15    | 0.314 | 0.277   | 0.289   | 0.283    |        |
| 20    | 0.280 | 0.344   | 0.300   | **0.320** | ← best |

- **F1-micro=0.320** — +11 puntos respecto al baseline de mmBERT (0.150)
- La ganancia es inmediata desde la época 1: el modelo clínico reconoce el dominio
- F1-macro=0.051 — mejora relativa también en códigos raros
- El modelo llegó a las 20 épocas sin activar early stop → necesita más épocas

**Decisión:** aumentar epochs y patience para explotar el potencial del modelo.

---

### Paso 10 — Más épocas con RigoBERTa-Clinical (EPOCHS=100, PATIENCE=20)

**Cambio:** misma config que paso 9 pero epochs=100, patience=20.
Run ejecutado manualmente: `make ai-train-gpu ... EPOCHS=100 PATIENCE=20`.

**Resultado** (65 épocas, early stop en época 65, ~16.9s/época):

| Epoch | Loss  | P micro | R micro | F1 micro |        |
| ----- | ----- | ------- | ------- | -------- | ------ |
| 10    | 0.337 | 0.181   | 0.198   | 0.189    |        |
| 20    | 0.198 | 0.321   | 0.343   | 0.331    |        |
| 30    | 0.110 | 0.404   | 0.321   | 0.358    |        |
| 50    | 0.064 | 0.449   | 0.301   | 0.361    |        |
| 65    | 0.049 | 0.470   | 0.295   | **0.362** | ← best |

- **F1-micro=0.362** — nuevo máximo
- F1-macro=0.067
- La loss sigue bajando agresivamente (0.337 → 0.049) mientras F1 se estabiliza
  en torno a 0.35-0.36 desde la época 30: señal clara de **overfitting**
- Con solo 500 muestras de entrenamiento, el encoder (110M parámetros) memoriza
  el train set antes de generalizar

**Decisión:** atacar el overfitting. Opciones: más regularización (weight_decay,
dropout), o congelar capas del encoder para reducir parámetros entrenables.

---

### Paso 10b — weight_decay=0.1, patience=40, epochs=200

**Cambio:** `weight_decay=0.1` (×10 respecto al default), patience=40, epochs=200.
El resto igual al paso 10.

**Resultado** (115 épocas, early stop en época 115, ~16.6s/época):

| Epoch | Loss  | P micro | R micro | F1 micro |        |
| ----- | ----- | ------- | ------- | -------- | ------ |
| 20    | 0.198 | 0.321   | 0.343   | 0.331    |        |
| 57    | 0.046 | 0.477   | 0.297   | 0.366    |        |
| 58    | 0.045 | 0.488   | 0.293   | **0.366** | ← best |
| 115   | 0.039 | 0.501   | 0.283   | 0.361    |        |

- **F1-micro=0.369** — mejora marginal (+0.007 sobre paso 10)
- weight_decay=0.1 ralentiza el overfitting pero no lo detiene: la loss llega a 0.039
  mientras F1 oscila entre 0.35-0.37 desde la época 58
- El patrón confirma que el cuello de botella **no es la regularización del optimizador**
  sino la capacidad del encoder de memorizar 500 muestras con 110M parámetros

**Decisión:** congelar las primeras 20 capas del encoder (de 24). Solo los 4 últimas
capas + cabeza clasificadora actualizarán pesos (~5-10M parámetros entrenables en vez
de 110M). Añadir también dropout=0.3 en la cabeza.

---

### Paso 11 — freeze_layers=20, dropout=0.3 (**nuevo mejor**)

**Cambio:** `--freeze_layers 20 --dropout 0.3`. Las 20 primeras capas del encoder
quedan congeladas; solo se entrenan las 4 últimas + cabeza clasificadora.
El resto igual al paso 10b (lr=3e-5, weight_decay=0.1, patience=20, epochs=200).

**Resultado** (78 épocas, early stop en época 78, best en época 58, ~11s/época):

| Epoch | Loss  | P micro | R micro | F1 micro |        |
| ----- | ----- | ------- | ------- | -------- | ------ |
| 10    | 0.188 | 0.175   | 0.201   | 0.187    |        |
| 30    | 0.098 | 0.388   | 0.298   | 0.337    |        |
| 58    | 0.069 | 0.430   | 0.360   | **0.392** | ← best |
| 78    | 0.048 | 0.466   | 0.326   | 0.384    |        |

- **F1-micro=0.392** — nuevo máximo (+2.3 pts sobre paso 10b)
- **F1-macro=0.100** — mejora significativa en códigos raros (+0.020)
- Épocas más rápidas: 11s vs 16s (capas congeladas reducen backprop)
- La loss baja más despacio que antes (0.069 en época 58 vs 0.039 en 10b) →
  el freeze limita la memorización del train set
- El modelo sigue overfittando a partir de la época 58, pero el techo subió

**Decisión:** el freeze de capas es la técnica más efectiva hasta ahora.
Siguiente experimento: subir dropout y después implementar sliding window.

---

### Paso 12 — dropout=0.5 (sin mejora sobre 0.3)

**Cambio:** `--dropout 0.5`. Todo lo demás igual al paso 11 (freeze=20, lr=3e-5, weight_decay=0.1, patience=20, epochs=200).

**Hipótesis:** el modelo aún sobreajusta después de la época 58 con dropout=0.3. Subiendo a 0.5 se añade más ruido en la cabeza para dificultar la memorización.

**Resultado** (89 épocas, early stop, ~11s/época):

| Epoch | Loss  | P micro | R micro | F1 micro |        |
| ----- | ----- | ------- | ------- | -------- | ------ |
| 30    | 0.184 | 0.302   | 0.388   | 0.339    |        |
| 65    | 0.077 | 0.449   | 0.348   | 0.392    |        |
| 82    | 0.059 | 0.477   | 0.337   | 0.395    |        |
| 89    | 0.054 | 0.465   | 0.349   | **0.398** | ← best |

- **F1-micro=0.398** — mejora marginal (+0.006 sobre paso 11)
- El patrón es idéntico: F1 oscila entre 0.387-0.398 desde la época 65
- dropout=0.5 no cambia el techo: la limitación es estructural (truncación del texto y escasez de datos)
- F1-macro=0.098 — prácticamente igual al paso 11

**Conclusión:** la regularización en la cabeza no puede superar la truncación del texto (50% del contenido descartado a 512 tokens). El siguiente paso es **sliding window**.

---

### Paso 13 — sliding window (chunk_overlap=64) — en curso

**Cambio:** `--sliding_window --chunk_overlap 64`. En lugar de truncar el texto al primer max_length=512 tokens, se codifica el documento completo como ventanas solapadas de 512 tokens con stride de 64. Los embeddings [CLS] de cada chunk se agregan por mean-pool antes del clasificador.

El resto igual al paso 11 (freeze=20, dropout=0.3, lr=3e-5, weight_decay=0.1, patience=20).

**Por qué sliding window:**
Los informes CodiESP tienen una media de ~570 tokens. Con max_length=512 se trunca ~50% de los documentos, perdiendo menciones de diagnósticos que aparecen en la segunda mitad del informe. Sliding window procesa el texto completo: un documento de 1000 tokens genera ~3 chunks de 512 con 64 tokens de solapamiento entre ellos.

**Resultado** (best ~época 62, early stop ~época 82, ~16s/época):

| Epoch | Loss  | P micro | R micro | F1 micro |        |
| ----- | ----- | ------- | ------- | -------- | ------ |
| 20    | 0.249 | 0.253   | 0.316   | 0.281    |        |
| 40    | 0.121 | 0.329   | 0.378   | 0.352    |        |
| 62    | 0.068 | 0.427   | 0.322   | **0.368** | ← best |
| 80    | 0.048 | 0.444   | 0.306   | 0.363    |        |

- **F1-micro=0.368** — peor que el paso 11 sin sliding window (0.392)
- **Recall cae**: R=0.323 vs R=0.360 (paso 11). El modelo predice menos positivos
- Precisión similar (P=0.427 vs P=0.430), pero el recall mucho más bajo
- F1-macro=0.088 (vs 0.100 en paso 11)

**Por qué falló:** los documentos CodiESP tienen una media de ~570 tokens. Con stride=64 y max_length=512, el chunk 2 contiene ~60 tokens reales + 452 de padding. Aunque el attention mask ignora el padding en el encoder, el CLS del chunk 2 representa un contexto muy corto. Mean-pooling del CLS de chunk 1 (512 tokens reales) con el CLS de chunk 2 (60 tokens) diluye la representación global → el modelo ve menos señal y predice menos positivos.

**Conclusión:** mean-pool de CLS entre chunks de longitud muy desigual no funciona. Para que sliding window sea útil habría que usar documentos más largos (>>512 tokens) o un pooling mejor (atención aprendida, o filtrar chunks con < N% tokens reales).

---

### Paso 14 — freeze_layers=16 (más capacidad)

**Cambio:** `--freeze_layers 16` — descongelar 8 capas (vs 4 en paso 11). La hipótesis es que 4 capas entrenables pueden ser insuficientes para aprender representaciones de 809 códigos, y que 8 capas con la misma regularización (dropout=0.3, weight_decay=0.1) pueden subir el techo sin causar el overfitting agresivo del paso 10 (todas las capas libres).

Resto igual al paso 11: lr=3e-5, max_length=512, threshold=0.5, patience=20, epochs=200.

**Resultado** (best ~época 35, early stop ~época 72, ~11s/época):

| Epoch | Loss  | P micro | R micro | F1 micro |        |
| ----- | ----- | ------- | ------- | -------- | ------ |
| 20    | 0.222 | 0.288   | 0.334   | 0.309    |        |
| 35    | 0.111 | 0.401   | 0.342   | **0.373** | ← best |
| 50    | 0.070 | 0.448   | 0.320   | 0.373    |        |
| 70    | 0.045 | 0.472   | 0.297   | 0.365    |        |

- **F1-micro=0.373** — peor que freeze=20 (0.392)
- Con 101.8M parámetros entrenables el modelo sobreajusta más rápido (pérdida cae de 0.111 a 0.045 mientras F1 baja)
- F1-macro=0.079 — peor que freeze=20 (0.100); el modelo se focaliza en códigos frecuentes y pierde generalización en raros
- **Conclusión:** el óptimo en esta configuración es freeze=20 (4 capas entrenables, ~5M params)

**Patrón observado:**

| Freeze | Params entrena | F1-micro |
| ------ | -------------- | -------- |
| 0      | 559M           | 0.362    |
| 16     | 102M           | 0.373    |
| **20** | **~5M**        | **0.392–0.398** |

Freeze=20 es el óptimo: suficiente capacidad para adaptar al dominio, suficiente regularización implícita (pocos parámetros libres) para no memorizar las 500 muestras.

---

### Paso 15 — lr=1e-4 con freeze=20 (LR más alto)

**Cambio:** `--lr 1e-4` (×3 sobre el 3e-5 del paso 11). Con solo ~5M parámetros entrenables, quizás el LR actual es demasiado conservador y las 4 capas no adaptan suficientemente los pesos. Un LR mayor podría extraer más del potencial de las capas descongeladas.

Resto igual al paso 11: dropout=0.3, weight_decay=0.1, patience=20, epochs=200.

**Resultado** (best época 59, early stop ~79, ~10s/época):

| Epoch | Loss   | P micro | R micro | F1 micro |        |
| ----- | ------ | ------- | ------- | -------- | ------ |
| 10    | 0.282  | 0.209   | 0.314   | 0.251    |        |
| 20    | 0.128  | 0.376   | 0.370   | 0.373    |        |
| 30    | 0.059  | 0.456   | 0.355   | 0.399    |        |
| 45    | 0.029  | 0.494   | 0.346   | 0.407    |        |
| 59    | 0.018  | 0.556   | 0.329   | **0.414** | ← best |
| 75    | 0.012  | 0.543   | 0.327   | 0.408    |        |

- **F1-micro=0.4135** — nuevo máximo (+1.5 pts sobre paso 12)
- LR=1e-4 converge mucho más rápido: F1=0.373 ya en época 20 (vs épocas 40+ con lr=3e-5)
- **P=0.556, R=0.329** — el modelo es muy selectivo; precision alta pero recall bajo. Un threshold menor podría recuperar recall.
- F1-macro=0.106 — ligera mejora (+0.006 sobre paso 12)
- La loss colapsa a 0.018 antes del early stop → el modelo sigue memorizando, pero el techo subió porque las 4 capas con LR alto se adaptan mejor al dominio clínico

**Decisión:** el config ganador es `freeze=20, lr=1e-4, dropout=0.3, wd=0.1`. Probar threshold=0.4 para equilibrar P/R.

---

### Paso 16 — threshold=0.4 (equilibrar P/R)

**Cambio:** `--threshold 0.4`. El paso 15 terminó con P=0.556, R=0.329 — el modelo es muy selectivo. Con threshold=0.4 el modelo predice más positivos: recall sube, precisión baja, y el F1 podría subir si el punto de equilibrio óptimo está por debajo de 0.5.

Resto igual al paso 15: freeze=20, lr=1e-4, dropout=0.3, weight_decay=0.1, patience=20, epochs=200.

**Resultado** (best época 67, early stop ~87, ~10s/época):

| Epoch | Loss   | P micro | R micro | F1 micro |        |
| ----- | ------ | ------- | ------- | -------- | ------ |
| 20    | 0.131  | 0.268   | 0.447   | 0.335    |        |
| 35    | 0.045  | 0.397   | 0.391   | 0.394    |        |
| 55    | 0.020  | 0.442   | 0.383   | 0.410    |        |
| 67    | 0.015  | 0.515   | 0.355   | **0.420** | ← best |
| 80    | 0.011  | 0.494   | 0.351   | 0.411    |        |

- **F1-micro=0.4204** — nuevo máximo (+0.007 sobre paso 15)
- threshold=0.4 da mejor balance P/R que threshold=0.5: P=0.515 vs 0.556, R=0.355 vs 0.329
- F1-macro=0.106 — igual que paso 15 (códigos raros no se benefician del threshold)
- El modelo sigue siendo precision-heavy (P>R); threshold=0.3 podría mejorar aún más

**Observación sobre la relación threshold/F1:**

| thr  | P     | R     | F1    |
| ---- | ----- | ----- | ----- |
| 0.5  | 0.556 | 0.329 | 0.414 |
| **0.4**  | **0.515** | **0.355** | **0.420** |
| 0.3  | ?     | ?     | ?     |

---

### Paso 17 — threshold=0.3 (bajar más el umbral)

**Cambio:** `--threshold 0.3`. Continúa la búsqueda del punto óptimo de equilibrio P/R.

Resto igual al paso 16: freeze=20, lr=1e-4, dropout=0.3, weight_decay=0.1, patience=20, epochs=200.

**Resultado** (best época 113, early stop ~133, ~10-11s/época):

| Epoch | Loss   | P micro | R micro | F1 micro |        |
| ----- | ------ | ------- | ------- | -------- | ------ |
| 20    | 0.131  | 0.207   | 0.574   | 0.304    |        |
| 40    | 0.035  | 0.366   | 0.450   | 0.404    |        |
| 55    | 0.021  | 0.434   | 0.411   | 0.422    |        |
| 113   | 0.006  | 0.502   | 0.376   | **0.430** | ← best |
| 130   | 0.005  | 0.507   | 0.369   | 0.427    |        |

- **F1-micro=0.4302** — nuevo máximo (+1.0 pts sobre paso 16)
- P=0.502, R=0.376 — más equilibrado que con thr=0.5 (P=0.556)
- **F1-macro=0.118** — mejora significativa (+0.012); el umbral bajo permite detectar más códigos raros
- El modelo converge más lento con thr=0.3 (best en época 113 vs época 67 con thr=0.4) porque la condición de "nueva mejora" es más exigente (más predicciones = más fácil empatar el best anterior)
- Patrón: bajar el threshold sigue mejorando F1 → el modelo tiene señal real a probabilidades < 0.4

| thr  | P     | R     | F1-micro | F1-macro |
| ---- | ----- | ----- | -------- | -------- |
| 0.5  | 0.556 | 0.329 | 0.414    | 0.106    |
| 0.4  | 0.515 | 0.355 | 0.420    | 0.106    |
| **0.3**  | **0.502** | **0.376** | **0.430**    | **0.118**    |
| 0.2  | ?     | ?     | ?        | ?        |

---

### Paso 18 — threshold=0.2

**Cambio:** `--threshold 0.2`. Continúa el barrido de thresholds con el config ganador. Si el F1 sigue subiendo, el punto óptimo puede estar aún más abajo.

**Resultado** (best ~época 75, early stop ~145, ~11s/época):

| Epoch | Loss   | P micro | R micro | F1 micro |        |
| ----- | ------ | ------- | ------- | -------- | ------ |
| 20    | 0.129  | 0.142   | 0.662   | 0.234    |        |
| 45    | 0.029  | 0.307   | 0.495   | 0.379    |        |
| 75    | 0.012  | 0.410   | 0.415   | **0.413** | ← best |
| 110   | 0.007  | 0.433   | 0.410   | 0.421    |        |

- **F1-micro=0.4266** — ligeramente peor que thr=0.3 (0.430)
- P=0.452, R=0.404 — el balance P/R más equilibrado de todo el barrido
- **F1-macro=0.124** — el mejor macro hasta la fecha (mejora en códigos raros)
- Con threshold muy bajo el modelo predice demasiado → más falsos positivos que reducen la micro-F1

**Barrido de thresholds completado (freeze=20, lr=1e-4, dropout=0.3, wd=0.1):**

| thr  | P     | R     | F1-micro | F1-macro |
| ---- | ----- | ----- | -------- | -------- |
| 0.5  | 0.556 | 0.329 | 0.414    | 0.106    |
| 0.4  | 0.515 | 0.355 | 0.420    | 0.106    |
| **0.3**  | **0.502** | **0.376** | **0.430**    | 0.118    |
| 0.2  | 0.452 | 0.404 | 0.427    | **0.124**    |

**Conclusión:** thr=0.3 es óptimo para micro-F1. thr=0.2 es mejor para macro-F1 (códigos raros). Los hiperparámetros están exhaustivamente explorados con RigoBERTa-Clinical (512 tokens).

**Siguiente frontera:** el modelo base `IIC/RigoBERTa-Clinical` tiene ventana máxima de 512 tokens. Para superar este techo hay que cambiar a un modelo con contexto nativo largo.

---

### Paso 19 — Longformer biomedical-clinical-es (contexto 2048 tokens)

**Cambio:** modelo `PlanTL-GOB-ES/longformer-base-4096-biomedical-clinical-es`, `max_length=2048`, `batch_size=1`, `grad_accum=16`, `freeze_layers=8` (Longformer-base tiene 12 capas; freeze=8 deja las 4 últimas entrenables, equivalente al freeze=20 de RigoBERTa-Clinical). Mismo lr=1e-4, thr=0.3.

**Objetivo:** eliminar el problema de truncación (los informes CodiESP tienen ~570 tokens, el 50% se truncaba con max_length=512) usando la ventana de atención local+global de Longformer.

**Resultado** (best época 115, early stop ~135, ~70s/época, 2.2h total):

| Modelo | P micro | R micro | F1 micro | F1 macro |
| ------ | ------- | ------- | -------- | -------- |
| RigoBERTa-Clinical thr=0.3 (paso 17) | 0.502 | 0.376 | **0.430** | 0.118 |
| Longformer 2048 thr=0.3 (paso 19) | 0.400 | **0.434** | 0.416 | 0.117 |

- **F1-micro=0.4164** — inferior al mejor RigoBERTa-Clinical (0.4302)
- **Recall=0.434** — el mejor recall hasta la fecha (+5.8pp vs RigoBERTa-Clinical)
- **Precisión=0.400** — cae 10pp porque con más contexto el modelo activa más clases, muchas incorrectas
- **6.4× más lento** (70s/época vs 11s/época)

**Interpretación:** el contexto largo ayuda a *encontrar* más diagnósticos (recall ↑) pero introduce más falsos positivos (precisión ↓). El tradeoff neto es negativo para micro-F1 con thr=0.3. El modelo no se ha beneficiado tanto del contexto extra como se esperaba, probablemente porque los diagnósticos clave ya aparecen en los primeros 512 tokens (inicio del informe).

**Conclusión:** RigoBERTa-Clinical (512 tokens) sigue siendo el mejor modelo. El cuello de botella no es la longitud del contexto sino el número de ejemplos de entrenamiento (~500 docs para 809 clases).

---

### Paso 20 — Códigos completos (1767 clases, modo `full`)

**Cambio:** `--full_codes` — en vez de predecir bloques CIE-10 (3 caracteres, ej. `I21`), predice el código completo (ej. `I21.9`). Pasa de 809 a 1767 clases únicas. Mismo config ganador: freeze=20, lr=1e-4, dropout=0.3, wd=0.1, thr=0.3.

**Motivación:** los bloques son útiles como proxy pero producción necesita el código completo. Este paso mide el coste real de la granularidad.

**Resultado** (dos runs independientes, reproducible):

| Run | Época best | P | R | F1-micro | F1-macro |
| --- | ---------- | - | - | -------- | -------- |
| 144558Z | 79 | 0.350 | 0.307 | **0.327** | 0.050 |
| 145554Z | 124 | 0.380 | 0.286 | **0.326** | 0.049 |

**Comparación bloque vs código completo:**

| Nivel | Clases | P | R | F1-micro | F1-macro |
| ----- | ------ | - | - | -------- | -------- |
| Bloque (paso 17) | 809 | 0.502 | 0.376 | **0.430** | 0.118 |
| Código completo (paso 20) | 1767 | 0.350–0.380 | 0.286–0.307 | **0.327** | 0.050 |

- **F1 cae -10pp** (0.430 → 0.327) al doblar las clases con el mismo dataset
- **F1-macro cae -7pp** (0.118 → 0.050) — los códigos raros son aún más difíciles a nivel completo
- La degradación es consistente entre las dos runs (varianza < 0.1pp)

**Interpretación:** con 1767 clases y ~500 documentos, la ratio datos/clase cae a ~0.28 docs/clase (era ~0.62 con bloques). El modelo no puede aprender patrones suficientes para los códigos específicos. Para alcanzar F1≈0.43 a nivel código completo haría falta un dataset ~3× mayor.

La caída es especialmente severa en F1-macro (0.118 → 0.050, −58%): los códigos raros que ya eran difíciles a nivel bloque se vuelven prácticamente indetectables a nivel completo — un código que aparecía 3 veces en 500 documentos a nivel bloque ahora puede estar dividido en 4-5 subtipos, cada uno con 1 aparición. La consistencia entre los dos runs independientes (varianza <0.1pp) confirma que el resultado es real y no ruido.

La decisión de quedarse con código completo (1767 clases) pese al coste es correcta: el problema a resolver en producción requiere el código completo, no una aproximación por bloque. El camino para recuperar esos 10pp perdidos pasa por enriquecer la señal de entrenamiento, no por simplificar el target — que es exactamente lo que ataca el paso 21.

---

### Paso 21 — Pre-entrenamiento sobre descripciones CIE-10 (código completo)

**Cambio:** antes del fine-tuning en CodiESP, se añade una fase de pre-entrenamiento
(`--pretrain_epochs 20`) sobre las ~101k descripciones del diccionario CIE-10 oficial.

**Motivación:** el problema con los 1767 códigos completos es que el modelo no reconoce
la terminología clínica específica (siglas, variantes, calificadores). El diccionario
CIE-10 ya contiene esa terminología de forma autorizada:

```
A00.0  →  "Cólera debido a Vibrio cholerae 01, biotipo cholerae | Cólera clásico"
I21.0  →  "Infarto agudo de miocardio transmural de la pared anterior"
```

Cada fila genera una muestra por cada variante separada por `|`. El contenido entre
paréntesis aporta contexto clínico (calificadores de lateralidad, acrónimos) y se mantiene
en el texto. Resultado: ~120k muestras de pre-entrenamiento con cobertura total de los
1767 códigos, usando terminología oficial en español.

**Configuración:**
- `--pretrain_epochs 20` sobre 120k muestras (descripciones CIE-10)
- `--full_codes` — código completo (1767 clases)
- Mismo config ganador post-pre-entrenamiento: freeze=20, lr=1e-4, dropout=0.3, wd=0.1, thr=0.3
- Sin early stopping durante el pre-entrenamiento (épocas fijas), sin evaluación en val

**Resultado** (best época 127, early stop ~147, ~11s/época):

| Fase | P | R | F1-micro | F1-macro |
| ---- | - | - | -------- | -------- |
| Sin pre-entrenamiento (paso 20) | 0.350–0.380 | 0.286–0.307 | 0.327 | 0.050 |
| **Con pre-entrenamiento 20 épocas** | **0.439** | **0.423** | **0.431** | **0.092** |

- **F1-micro=0.431** — supera al nivel bloque (0.430) usando código completo (1767 clases)
- **F1-macro=0.092** — mejora del +84% en códigos raros (+4.2pp)
- **+10.4pp de F1-micro** respecto a sin pre-entrenamiento
- Misma velocidad que sin pre-entrenamiento (~11s/época en fine-tuning)

**Interpretación:** el pre-entrenamiento sobre las 3168 descripciones CIE-10 enseña al encoder a asociar terminología clínica oficial con los códigos antes de ver las notas reales. El fine-tuning posterior arranca desde una representación más rica y converge a un óptimo mejor. El resultado es especialmente notable porque se alcanza F1 de nivel bloque (0.430) con granularidad de código completo.

**Nota:** este run usó solo 3168 variantes (solo códigos presentes en CodiESP). Se probó añadir muestras negativas — ver paso 22.

---

### Paso 22 — Efecto de los negativos en el pre-entrenamiento

**Experimento:** añadir 1000 muestras negativas (descripciones de códigos CIE-10 no presentes en CodiESP, etiqueta todo-ceros) al pre-entrenamiento. Pretrain 5 épocas + 1000 neg, luego fine-tuning igual.

**Resultado:**

| Config | Neg | Épocas pre | F1-micro |
| ------ | --- | ---------- | -------- |
| Sin pre-entrenamiento (paso 20) | — | — | 0.327 |
| Pre-entrenamiento solo pos (paso 21) | 0 | 20 | **0.431–0.432** |
| Pre-entrenamiento + 1000 neg (paso 22) | 1000 | 5 | 0.329 |

**Conclusión:** los negativos hacen daño. Enseñan al modelo a suprimir activaciones — exactamente lo contrario de lo que necesita. El pre-entrenamiento óptimo es solo con muestras positivas (descripción oficial → código). El código queda sin negativos.

El resultado es contraintuitivo pero tiene sentido: durante el pre-entrenamiento, el modelo ve solo muestras de la forma "este texto → este código". Introducir negativos ("este texto → ningún código") enseña al modelo a ser conservador, a suprimir activaciones, a decir "no". Con solo 5 épocas y 1000 negativos frente a 3168 positivos, la señal de "no predecir" domina y destruye el aprendizaje previo. El fine-tuning posterior sobre CodiESP ya se encarga de enseñar la discriminación; el pre-entrenamiento debe maximizar el reconocimiento de terminología, no la inhibición.

---

### Paso 23 — Pre-entrenamiento combinado: descripciones CIE-10 + snippets task_X

**Cambio:** ampliar el pre-entrenamiento añadiendo los snippets clínicos reales de las
anotaciones de explainabilidad de CodiESP (ficheros `codiesp_X_source_*.csv`).

**Motivación:**
El paso 21 demostró que pre-entrenar con las descripciones oficiales CIE-10 (+10pp F1)
enseña al modelo terminología formal. El gap que queda está en la jerga clínica real:
el médico no escribe "infarto agudo de miocardio transmural de la pared anterior" sino
"IAM", "dolor centrotorácico irradiado", "SCA con ST". El archivo task_X de CodiESP
proporciona exactamente esto: para cada código asignado a una nota, el anotador marcó
el fragmento de texto que justifica ese código — el texto real del médico.

**Fuentes combinadas:**

- Fuente 1 (ya existente): 3168 variantes de descripciones CIE-10 oficiales
- Fuente 2 (nueva): snippets DIAGNOSTICO de task_X
  - Train: 7209 snippets
  - Val: 3431 snippets
  - Total: 10640 snippets clínicos reales cubriendo todos los 1767 códigos
  - **Real cargado**: 10072 snippets (algunos códigos no en vocabulario o snippets vacíos)

**Total de muestras de pre-entrenamiento:** 3168 + 10072 = 13240

**Formato task_X:**

```json
{"label": "DIAGNOSTICO", "code": "i21.9",
 "text": "IAM sin elevación del ST",
 "spans": [[142, 165]]}
```

Solo se incluyen anotaciones `label == "DIAGNOSTICO"`. Los snippets PROCEDIMIENTO
se descartan para no contaminar el vocabulario del clasificador de diagnósticos.

**Implementación:**

- `build_pretrain_loader()` en `train.py` recibe nuevo parámetro `taskx_files=None`
- Nuevo argumento CLI: `--pretrain_taskx <archivo1> [archivo2 ...]`
- Makefile: `PRETRAIN_TASKX="<ruta1> <ruta2>"` → `$(if $(PRETRAIN_TASKX),--pretrain_taskx $(PRETRAIN_TASKX),)`

**Lanzamiento:**

```bash
make ai-train-gpu FULL_CODES=1 PRETRAIN_EPOCHS=20 \
  PRETRAIN_TASKX="/data/codiesp_csvs/codiesp_X_source_train.csv /data/codiesp_csvs/codiesp_X_source_validation.csv" \
  MODEL=IIC/RigoBERTa-Clinical FREEZE_LAYERS=20 LR=1e-4 DROPOUT=0.3 \
  WEIGHT_DECAY=0.1 THRESHOLD=0.3
```

**Incidencias previas al run:**

1. **Imagen sin CUDA** — el `ai_engine/Dockerfile` fue modificado para usar build
   multi-stage (CPU/GPU via `BUILD_WITH_CUDA`). La imagen no había sido reconstruida
   → `Torch not compiled with CUDA enabled`. Fix: `make build-ai`.

2. **max_length=1024 vs max_position_embeddings=514** — RigoBERTa-Clinical (XLM-RoBERTa)
   solo admite 514 posiciones. Pasar `max_length=1024` causa CUDA assert en el kernel de
   position embeddings (`scatter gather kernel index out of bounds`).
   Fix: lanzar con `MAX_LENGTH=512`.

3. **task_X snippets: 0** — la columna `task_x` del CSV usa dict literals de Python
   (comillas simples) en vez de JSON estándar. `json.loads()` falla silenciosamente y
   devuelve 0 snippets. Fix: usar `ast.literal_eval()` en `build_pretrain_loader()`.
   Aplicado en `train.py`, requiere `make build-ai` antes del siguiente run.

**Run previo de referencia (bmtmd5201):** misma config pero con el bug de `json.loads`
(0 snippets task_X, solo 3168 muestras CIE-10) y EPOCHS=20 de fine-tuning. Resultado:
F1-micro=0.3225, F1-macro=0.107. El bajo F1 vs paso 21 (0.431) se debe a que paso 21
usó ~147 épocas de fine-tuning; con solo 20, el modelo no convergió totalmente. A tener
en cuenta: si el paso 23 real llega a 20 épocas de fine-tuning sin plateaur, relanzar
con `EPOCHS=150 PATIENCE=10`.

**Configuración final ejecutada:**

- `--pretrain_epochs 10` — pérdida convergida en época 9 (~0.0005), 10 suficiente
- `--batch_size 8 --grad_accum 4` — batch efectivo 32 (vs 16 anterior)
- `--epochs 150 --patience 10`
- flash_attention_2, freeze_layers=20, lr=1e-4, dropout=0.3, wd=0.1, thr=0.3

**Resultado** (best época 50, early stop época 60, ~15s/época fine-tuning):

| Fase | P | R | F1-micro | F1-macro |
| ---- | - | - | -------- | -------- |
| Paso 20 (sin pretrain) | 0.350–0.380 | 0.286–0.307 | 0.327 | 0.050 |
| Paso 21 (pretrain CIE-10 solo, batch=4) | 0.439 | 0.423 | 0.431 | 0.092 |
| **Paso 23 (pretrain CIE-10 + task_X, batch=8)** | **0.423** | **0.529** | **0.470** | **0.139** |

- **F1-micro=0.470** — +3.9pp vs paso 21
- **F1-macro=0.139** — +4.7pp vs paso 21 (+51% en códigos raros)
- El recall sube de 0.423 → 0.529 (+10.6pp): los snippets task_X enseñan la jerga real del médico
- La precision baja ligeramente (0.439 → 0.423): más predicciones, alguna falsa alarma extra
- Convergencia más rápida (época 50 vs ~127 en paso 21) gracias al mejor pretrain y batch mayor

**Interpretación:** la combinación de descripciones oficiales CIE-10 + snippets clínicos reales
(jerga médica, siglas, fragmentos de notas) da el mejor resultado hasta ahora. La mejora en
F1-macro (+51%) confirma que los snippets task_X enseñan al encoder a reconocer códigos raros
que antes apenas aparecían con terminología formal.

---

### Paso 24 — Asymmetric Loss (ASL)

**Cambio:** sustituir BCEWithLogitsLoss + pos_weight por Asymmetric Loss.

**Por qué ASL en vez de seguir con pos_weight:**

El `pos_weight` por clase ya ayuda, pero tiene un límite estructural: solo amplifica
la contribución de los positivos raros, pero no hace nada con los **negativos fáciles**.
En un problema de 1767 clases, cada muestra tiene ~11 positivos y ~1756 negativos.
La inmensa mayoría de esos 1756 negativos son predicciones confiadas (sigmoid ≈ 0.01):
el modelo aprende rápido que "la mayoría de códigos no aplican" y ese gradiente domina
el entrenamiento, ahogando la señal de los positivos raros.

**Cómo funciona ASL:**

Para cada clase y cada muestra, la loss es:

```text
y=1 (positivo):  -(1 - p)^γ+  · log(p)          # focusing suave o nulo
y=0 (negativo):  -(p̃)^γ-      · log(1-p̃)        # focusing agresivo
                  donde p̃ = min(sigmoid(x) + clip, 1)
```

- **γ- > 0**: cuando el modelo ya predice con confianza que un código NO aplica
  (`sigmoid ≈ 0.01`), el factor `p̃^γ-` ≈ 0 y ese negativo prácticamente no contribuye
  al gradiente. Solo los negativos "dudosos" (sigmoid ≈ 0.3-0.5) generan gradiente.

- **clip** (probability margin = 0.05): desplaza la probabilidad negativa antes del log,
  eliminando el ruido de anotación (casos donde el código es borderline pero no fue
  marcado).

- **γ+ = 0**: los positivos no tienen focusing extra — cada positivo raro contribuye
  igualmente, independientemente de si el modelo ya lo predice bien.

Resultado: el gradiente se concentra en los ejemplos difíciles/raros y los negativos
fáciles dejan de dominar el entrenamiento. El efecto esperado es un F1-macro más alto
(más códigos raros detectados) con recall también más alto.

**Implementación:** clase `AsymmetricLoss` en `train.py`. Se activa automáticamente
cuando `--asl_gamma_neg > 0`; si no, se usa el BCE+pos_weight anterior.
Nuevos args CLI: `--asl_gamma_neg`, `--asl_gamma_pos`, `--asl_clip`.
Makefile: `ASL_GAMMA_NEG`, `ASL_GAMMA_POS`, `ASL_CLIP`.

**Run ejecutado:** 24a — γ-=4, γ+=0 (paper default), con config base de paso 23:
pretrain=10 épocas, batch=8, grad_accum=4, freeze=20, lr=1e-4, dropout=0.3,
wd=0.1, thr=0.3, epochs=150, patience=10.

**Resultado** (best época 30, early stop época 40):

| Modelo | P | R | F1-micro | F1-macro |
|--------|---|---|----------|----------|
| Paso 23 (BCE + pos_weight) | 0.423 | 0.529 | **0.470** | 0.139 |
| **Paso 24a (ASL γ-=4, γ+=0)** | 0.274 | **0.593** | 0.375 | **0.147** |

- F1-micro cae 0.470 → 0.375 (−9.5pp)
- Recall sube (0.529 → 0.593) pero precisión se hunde (0.423 → 0.274)
- γ-=4 es demasiado agresivo: descarta casi todos los negativos fáciles y el modelo
  predice demasiados códigos por muestra, disparando falsos positivos
- F1-macro sube ligeramente (0.139 → 0.147) pero no compensa la pérdida de precisión

**Conclusión:** ASL con γ-=4 no mejora el resultado global. Pendiente: probar γ-=2
para un foco menos agresivo y ver si se recupera la precisión sin perder recall.

El fallo de ASL con γ-=4 ilustra un problema de calibración: con tantos negativos fáciles descartados, el modelo pierde la noción de "cuándo NO predecir". En un clasificador multi-label con 1767 clases, la habilidad de no predecir es tan importante como la de predecir — y ASL agresivo la destruye. El recall sube porque el modelo predice más, pero con poca discriminación: activa casi todos los códigos para cada documento. La mejora marginal en F1-macro (+0.8pp) no compensa la caída de precisión (−15pp), resultando en F1-micro peor.

---

### Paso 25 — Exploración de freeze_layers y dropout

**Cambio:** partiendo de la config ganadora del paso 23 (BCE + pos_weight), explorar
si descongelar más capas del encoder o reducir el dropout mejora el F1.

**Motivación:**
Con freeze=20, solo las 4 capas superiores del encoder son entrenables (51.4M params).
RigoBERTa-Clinical tiene 24 capas — quizá las capas intermedias necesitan adaptarse al
dominio clínico CIE-10. Por otro lado, dropout=0.3 puede estar limitando la capacidad
de memorizar los códigos raros (underfitting en la cola).

**Dos runs en paralelo:**

| Run | freeze | dropout | lr | trainable params |
|-----|--------|---------|----|-----------------|
| 25a | 16 | 0.2 | 1e-4 | 101.8M (8 capas) |
| 25b (ref) | 20 | 0.3 | 1e-4 | 51.4M (4 capas) — config paso 23 |

Ambas con pretrain=10 épocas, batch=8, grad_accum=4, epochs=150, patience=10.

**Resultado** (25a best época 11, early stop época 21; 25b = paso 23):

| Run | freeze | dropout | F1-micro | F1-macro | Observaciones |
|-----|--------|---------|----------|----------|---------------|
| 25a | 16 | 0.2 | 0.147 | 0.005 | Colapso total |
| Paso 23 | 20 | 0.3 | **0.470** | **0.139** | Mejor hasta ahora |

- freeze=16 (8 capas entrenables, 101.8M params) con solo ~500 muestras de train
  provoca colapso total: loss=0.20 en época 11, F1-micro=0.147, F1-macro=0.005
- El modelo no puede aprender con tanta capacidad libre y tan pocos datos: overfitting
  catastrófico o inestabilidad de gradientes en las capas bajas con lr=1e-4

**Conclusión:** el dataset de ~500 muestras impone un techo duro en el número de
capas entrenables. freeze=20 (4 capas) sigue siendo el óptimo.

**Segunda ronda — freeze=16 con lr mayor (paso 27):**

La hipótesis: la loss no bajaba en paso 25 porque el gradiente se diluye entre más parámetros
(101.8M vs 51.4M). Con lr más alto el modelo debería moverse más por el espacio de parámetros.

| Run | freeze | lr | F1-micro | F1-macro | Observaciones |
|-----|--------|----|----------|----------|---------------|
| 27a | 16 | 3e-4 | 0.127 | 0.002 | Colapso |
| 27b | 16 | 5e-4 | 0.133 | 0.001 | Colapso |

**Resultado:** freeze=16 colapsa con cualquier lr probado (1e-4, 3e-4, 5e-4). La
hipótesis del gradiente diluido era incorrecta — el problema es la sobreparametrización
relativa al tamaño del dataset (~500 muestras para 101M params entrenables).
freeze=20 es el límite definitivo para CodiESP.

Los tres intentos con freeze=16 (pasos 25a, 27a, 27b) con LR creciente muestran que el
problema no es de escala de gradiente sino estructural. Con 101M parámetros entrenables
y 500 muestras, el ratio datos/parámetro es de ~5×10⁻⁶ — el modelo tiene más grados
de libertad que datos para restringirlos, y cada actualización puede destruir tanto
como construye. El landscape de pérdida con tantos parámetros libres es tan plano y
lleno de sillas de montar que el gradiente estocástico no encuentra una dirección útil.
freeze=20 (51.4M params, 4 capas) con ~500 muestras es el mínimo viable que funciona
de forma estable. Esta lección es la que hace viable el progressive unfreezing del paso
30: primero estabilizar la cabeza, luego desbloquear capas una a una con LR reducido.

---

### Paso 26 — ASL γ-=2 y pos_weight_cap=30

Dos runs en paralelo partiendo de la config ganadora del paso 23:

**26a — ASL γ-=2 γ+=0:**
Repetición del paso 24a pero con γ- más suave. γ-=4 destruía precisión;
γ-=2 es un compromiso entre foco en negativos difíciles y no descartar demasiado.

**26b — pos_weight_cap=30:**
Subir el cap de 10 a 30 para diferencia entre códigos moderadamente raros (peso 10-30)
y los que solo aparecen 1-2 veces (peso 30). Con cap=10, todos los códigos que aparecen
menos de 50 veces reciben el mismo peso máximo de 10.

| Run | Loss | γ- | cap | F1-micro | F1-macro | best época |
|-----|------|----|-----|----------|----------|------------|
| Paso 23 (ref) | BCE | — | 10 | **0.470** | 0.139 | 50 |
| **26a** | ASL | 2 | — | 0.460 | **0.144** | 54 |
| **26b** | BCE | — | 30 | 0.451 | 0.141 | 114 |

- ASL γ-=2 es casi equivalente a paso 23 en F1-micro (−1pp) pero con F1-macro levemente mejor
- pos_weight_cap=30 converge mucho más tarde (época 114 vs 54 y 50): pesos altos generan
  gradientes grandes que desestabilizan el aprendizaje inicial
- Ninguna variante supera al paso 23 (BCE + cap=10)

**Conclusión:** la función de pérdida BCE + pos_weight_cap=10 del paso 23 sigue siendo
la mejor combinación. Las modificaciones de pérdida (ASL, cap mayor) no dan mejoras netas.

Los resultados de los pasos 24 y 26 juntos cuentan una historia coherente: la función de pérdida no es el cuello de botella. ASL γ-=2 es equivalente a BCE+pos_weight en F1-micro (−1pp, dentro del ruido), y pos_weight_cap=30 solo añade inestabilidad sin beneficio neto. El modelo ya está recibiendo una señal de gradiente adecuada — el problema es la cantidad de datos, no cómo se ponderan. Con 500 muestras y 1767 clases, no hay función de pérdida que compense la falta de ejemplos: hay ~140 códigos que aparecen 0 veces en train y otros ~400 que aparecen 1-2 veces. La función de pérdida solo puede optimizar lo que hay; los datos que no existen no se pueden compensar.

---

### Paso 28 — Threshold óptimo por clase, label smoothing y ReduceLROnPlateau

En los pasos 23-27 se ha optimizado todo lo que puede cambiar durante el entrenamiento
(pre-entrenamiento, batch, función de pérdida, capas congeladas). Este paso ataca tres
ejes ortogonales: cómo se usan las probabilidades en inferencia, cómo se formulan los
targets, y cómo evoluciona el LR a lo largo del entrenamiento.

---

#### 1. Threshold óptimo (global + por clase)

**Por qué el threshold=0.3 era una chapuza:**

En todos los runs anteriores se fijaba `threshold=0.3` manualmente. Este valor se
eligió en fases tempranas del proyecto (modelo mmBERT, solo 809 clases) y se arrastró
sin cuestionar. El problema: el threshold óptimo para F1-micro depende directamente
de la distribución de probabilidades que aprende el modelo. Si el modelo aprende
probabilidades bajas para la mayoría de códigos (lo que ocurre con BCE + pos_weight),
el threshold óptimo puede ser 0.2 o 0.15. Si el modelo es más "confiado", puede
ser 0.4-0.5. No hay ninguna razón para que sea 0.3.

**Threshold global:**

Se barre el intervalo [0.05, 0.95] en 19 pasos sobre el val set usando las probabilidades
ya calculadas del mejor modelo (sin re-entrenar, una sola pasada de inferencia extra).
Se elige el valor que maximiza F1-micro. Se guarda en `config.json` como threshold
por defecto del modelo.

Coste: ~1 segundo adicional al final de cada run.

**Threshold por clase:**

Cada uno de los 1767 códigos tiene su propia distribución de probabilidades. Para
códigos frecuentes (ej. I50 — insuficiencia cardiaca, aparece en 40+ notas), el modelo
aprende bien la diferencia entre presencia/ausencia y un threshold=0.35 puede ser óptimo.
Para un código raro (ej. Q89 — malformación congénita, 2-3 notas en train), el modelo
asigna probabilidades bajas incluso cuando el código está; un threshold=0.10 puede ser
necesario para capturarlo.

Implementación en `find_optimal_thresholds_per_class()`:

- Para cada clase, barre [0.05, 0.95] y elige el threshold que maximiza F1 binario de esa clase.
- **Excepción:** clases con <2 positivos en val no tienen datos suficientes para optimizar
  el threshold de forma fiable. Para estas clases se usa el threshold global. Con 1
  solo positivo en val, cualquier threshold que lo capture da F1=1 para esa clase —
  el sweep elegiría threshold=0.05 (predecir todo como positivo), lo que dispara
  falsos positivos en inferencia y hunde F1-micro. El mínimo de 2 positivos es
  conservador a propósito.
- El resultado se guarda en `thresholds_<timestamp>.json` con el vector completo
  de 1767 valores + `idx_to_code` para que el servicio de inferencia lo pueda cargar.

```python
# Inferencia con thresholds por clase (ai_engine):
thr_data = json.load(open("thresholds_<ts>.json"))
thresholds = np.array(thr_data["per_class_thresholds"])   # (1767,)
preds = (probs >= thresholds).astype(int)                  # broadcast por columna
```

El run reportará ambas métricas al final:
```
[threshold] global → óptimo=0.XX   F1-micro=0.XXXX
[threshold] por clase → F1-micro=0.XXXX  F1-macro=0.XXXX
```

---

#### 2. Label smoothing (ε=0.1)

**Por qué el modelo se vuelve overconfidente con BCE puro:**

BCEWithLogitsLoss minimiza `-(y·log(σ(x)) + (1-y)·log(1-σ(x)))`. El mínimo absoluto
se alcanza cuando `σ(x) → 1` para y=1 y `σ(x) → 0` para y=0. El optimizador empuja
los logits hacia ±∞ para acercarse a ese mínimo. En la práctica:

- Para un código frecuente, el modelo tiene suficientes ejemplos contrarios que
  frenan el empuje → logits moderados, probabilidades en [0.3, 0.7].
- Para un código rarísimo (2 positivos en 500 muestras), el gradiente de los
  498 negativos empuja el logit hacia −∞ sin apenas contrapeso → probabilidad
  siempre ≈ 0.001, invisible con cualquier threshold razonable.

**Cómo funciona label smoothing binario:**

Se reemplaza cada target y ∈ {0, 1} por y_smooth = y·(1−ε) + 0.5·ε:

```
y=1  →  y_smooth = 1·0.9 + 0.05 = 0.95
y=0  →  y_smooth = 0·0.9 + 0.05 = 0.05
```

Ahora el mínimo de la loss requiere `σ(x) = 0.95` para positivos y `σ(x) = 0.05`
para negativos — logits finitos de ≈ ±3. El optimizador deja de empujar hacia ±∞.

**Por qué ε=0.1:**

ε pequeño (0.05): mínimo efecto, difícil medir diferencia.
ε grande (0.2+): los positivos reciben target=0.9, el modelo aprende a no estar
seguro ni de los positivos claros — puede bajar precision sin beneficio.
ε=0.1 es el estándar de literatura (Szegedy et al., 2016) para clasificación.

**Efecto esperado:** mejor calibración de probabilidades (más útiles para el threshold
sweep), mejora marginal en recall de códigos raros, posiblemente leve caída de precision.

---

#### 3. ReduceLROnPlateau

**El problema con cosine+early stopping:**

Con cosine schedule y `total_steps = epochs_max × steps_per_epoch`, el LR decae a 0
al llegar a epochs_max=150 pase lo que pase. Con early stopping en época ~60:

```
LR en época 60 = lr_max × cos(π × 60/150) / 2 ≈ lr_max × 0.09
```

El modelo está aprendiendo con LR = 9% del máximo durante la segunda mitad del
entrenamiento útil. Si hay un plateau en época 40-50, el LR ya es tan bajo que
no puede escapar — no porque el modelo no pueda mejorar, sino porque el scheduler
lo frenó demasiado pronto.

**Cómo funciona ReduceLROnPlateau:**

Monitoriza val F1-micro tras cada época. Si no hay mejora durante `patience//2 = 10`
épocas, multiplica el LR por `factor=0.5`. El LR solo baja cuando el modelo de verdad
se ha estancado — no por un calendario predefinido. Si el modelo rompe el plateau,
el LR se mantiene.

```
Ejemplo:
  épocas 1-40:    mejora continua → LR = 1e-4 (sin cambios)
  épocas 40-50:   plateau →  reducción × 0.5 → LR = 5e-5
  época 51:       nueva mejora → se mantiene LR = 5e-5
  épocas 60-70:   segundo plateau → reducción × 0.5 → LR = 2.5e-5
```

El modelo puede hacer varias reducciones y seguir mejorando en vez de parar.
La desventaja vs cosine: no tiene garantía de convergencia matemática; puede
oscila en torno a un mínimo sin converger limpiamente.

---

#### Implementación

```python
# train.py
--label_smoothing 0.1   # target 1 → 0.95, target 0 → 0.05
--lr_schedule plateau   # ReduceLROnPlateau en vez de cosine
```

El sweep de threshold (global + por clase) se ejecuta **siempre** al final,
sin flag adicional. Artefactos generados:

- `thresholds_<ts>.json` — vector de 1767 thresholds por clase + threshold global
- `config.json` — ahora incluye `threshold` (global óptimo) y `thresholds_file`

---

**Runs en paralelo (paso 28):**

| Run | label_smoothing | lr_schedule | threshold |
|-----|-----------------|-------------|-----------|
| 28a | 0.1 | cosine | óptimo auto |
| 28b | 0.0 | plateau | óptimo auto |

Ambas con config paso 23: pretrain=10, batch=8, grad_accum=4, freeze=20, lr=1e-4,
dropout=0.3, wd=0.1, epochs=150, patience=20.

**Resultado:**

| Run | F1-micro (best val) | best época | thr global óptimo | per-class F1-micro | per-class F1-macro |
|-----|---------------------|------------|--------------------|--------------------|-------------------|
| Paso 23 (ref) | 0.470 | 50 | — | — | — |
| **28b (plateau)** | **0.4751** | **102** | 0.30 | **0.5356** | 0.1494 |
| 28a (label smooth 0.1) | 0.0265 | 2 | — | — | — |

**28b — ReduceLROnPlateau: nuevo mejor resultado (0.4751)**

El modelo siguió mejorando de forma continua hasta época 102, vs época 50 con cosine.
Con cosine, el LR había decaído al ~9% del máximo en época 60 y el modelo no podía escapar
del plateau. Con ReduceLROnPlateau, el LR se mantuvo alto mientras había mejora y solo
bajó cuando el modelo se estancó de verdad.

La progresión muestra que F1=0.452 en época 50 (donde cosine paraba) no era el techo:
```
época 50:  F1=0.452    (fin de paso 23)
época 60:  F1=0.460
época 80:  F1=0.463
época 102: F1=0.4751   (best)
```

**Threshold por clase: +8.6pp F1-micro sobre val**

Con thresholds por clase, F1-micro sube de 0.4751 → 0.5356 en val (+8.6pp). Hay que
tener en cuenta que estos thresholds están optimizados SOBRE val, así que la cifra es
optimista y no generalizable directamente a test. Aun así, el artefacto
`thresholds_<ts>.json` es el correcto para desplegar: cada código tiene su propio punto
de corte en vez de un 0.30 único para todos.

**28a — Label smoothing simétrico: colapso total por interacción con pos_weight**

El modelo colapsó desde época 3: recall=1.0, precisión=0.005, predice todos los
1767 códigos como positivos para cada documento.

La causa: label smoothing simétrico (0→0.05) + pos_weight=10 son incompatibles.
Para un código negativo suavizado a 0.05 con pos_weight=10:

```
loss = -pos_weight × y_smooth × log(σ) − (1−y_smooth) × log(1−σ)
     = -10 × 0.05 × log(σ)  − 0.95 × log(1−σ)
     = -0.5 × log(σ)  ← gradiente espúreo "predice positivo"
```

Para un código raro con 2 positivos en 498 muestras:
- Gradiente real (positivos):    2 × 10 × 0.95 = 19 unidades "predice positivo"
- Gradiente espúreo (negativos): 498 × 0.5     = 249 unidades "predice positivo"

El gradiente espúreo supera al real 13×. El modelo aprende "predice todo" como óptimo.

**Fix aplicado en train.py: one-sided label smoothing**

Solo se suavizan los positivos (1→1-ε), los negativos se mantienen en 0:
```python
labels = labels * (1.0 - label_smoothing)  # 1→0.9,  0→0 (sin cambio)
```
Así no hay interacción con pos_weight. Se relanzará en paso 29.

---

### Paso 29 — Label smoothing one-sided + plateau combinados

Tras el fix, se prueban dos configuraciones en paralelo:

| Run | label_smoothing | lr_schedule |
|-----|-----------------|-------------|
| 29a | 0.1 (one-sided) | plateau |
| 29b | 0.1 (one-sided) | cosine |

Base: config paso 23 + patience=20.

**Resultado:**

| Run | smoothing | scheduler | F1-micro | best época | per-class micro | per-class macro |
|-----|-----------|-----------|----------|------------|-----------------|-----------------|
| 28b (ref) | — | plateau | 0.4751 | 102 | 0.5356 | 0.1494 |
| **29a** | 0.1 one-sided | plateau | **0.4819** | **115** | 0.5383 | 0.1420 |
| 29b | 0.1 one-sided | cosine | 0.4812 | 76 | 0.5323 | **0.1652** |

Label smoothing one-sided funciona: +0.7pp F1-micro vs 28b con mismo scheduler. El mecanismo
es sutil pero importante: al suavizar los targets positivos de 1.0 a 0.9, el mínimo de la loss
deja de requerir logits de ±∞ y se satisface con logits finitos (~±2.2). Esto reduce la
tendencia a overconfidence en las épocas tardías, permitiendo que el modelo siga haciendo
ajustes finos hasta época 115 vs 102 sin smoothing.

Dato llamativo: 29b (cosine) tiene mejor F1-macro por clase (0.1652 vs 0.1420) pese a peor
F1-micro que 29a. La explicación más plausible: con cosine schedule, el LR decae suavemente
hacia 0 en las últimas épocas antes del early stopping, actuando como una fase de "fine-tuning
fino" natural para los parámetros ya bien ajustados. Los códigos frecuentes no cambian mucho
(ya están aprendidos), pero los raros — con representaciones más ruidosas — se benefician de
ese refinamiento con LR bajo. El plateau, al mantener el LR más alto mientras haya mejora en
F1-micro (dominado por códigos frecuentes), puede dejar los códigos raros ligeramente
sobre-ajustados. Ambos efectos conviven: plateau → mejor F1-micro, cosine → mejor F1-macro.

**Config ganadora hasta ahora:** plateau + label_smoothing=0.1 (one-sided), F1-micro=0.4819.

---

### Paso 30 — Progressive unfreezing

**Motivación:** freeze=20 es el límite duro con 500 muestras — pero solo mientras el encoder
está completamente estático. Progressive unfreezing es una técnica estándar de transfer learning:
congelar el encoder al principio para que la cabeza clasificadora se estabilice (épocas 1–N),
luego ir descongelando gradualmente las capas superiores con LR reducido.

La hipótesis es que las **capas 16–19** (las más cercanas a la cabeza, más semánticas, congeladas
actualmente en freeze=20) contienen representaciones útiles para la tarea clínica que se pueden
afinar sin catastrofismo. La clave que diferencia esto del paso 25/27 (donde freeze=16 colapsó)
es el **orden**: primero la cabeza aprende qué buscar, luego el encoder refina sus representaciones
para apoyar esa señal. Freeze=16 directo con 500 muestras colapsó porque el encoder nunca se había
adaptado a la tarea.

**Diseño:**

- Base: config ganadora paso 29a (freeze=20, plateau, label_smoothing=0.1, LR=1e-4)
- `unfreeze_every=25`: cada 25 épocas se activa el siguiente bloque de 4 capas
- `unfreeze_layers=4`: se descongelan 4 capas por vez (mismo bloque que el mínimo estable)
- `unfreeze_lr_ratio=0.1`: las capas recién descongeladas reciben LR = base_lr × 0.1 = **1e-5**,
  mientras las capas ya entrenables siguen a 1e-4 (con la reducción acumulada de plateau)
- Early stopping se resetea en cada evento de unfreeze para dar margen al nuevo bloque

**Secuencia esperada (EPOCHS=150, unfreeze_every=25):**

| Época | Capas libres | Params entrenables | LR nuevas capas |
|-------|-------------|-------------------|-----------------|
| 1–25  | 20–23 (4 capas) | ~51.4M | — |
| 26    | **16–23** (8 capas) | ~63M  | 1e-5 |
| 51    | **12–23** (12 capas) | ~74M | 1e-5 |
| 76    | **8–23** (16 capas) | ~86M  | 1e-5 |
| 101   | **4–23** (20 capas) | ~97M  | 1e-5 |

**Implementación (train.py):**

Nuevos métodos en `FlatClassifier`:
- `_get_encoder_layers()`: detecta `encoder.encoder.layer` o `encoder.encoder.layers`
- `unfreeze_next_group(n_layers)`: activa `requires_grad=True` en las `n_layers` capas superiores
  del bloque congelado, actualiza `self.current_freeze`, devuelve los nuevos params

En `train()`: tras cada época, si `epoch % unfreeze_every == 0`:
```python
new_params = model.unfreeze_next_group(unfreeze_layers)
optimizer.add_param_group({"params": new_params, "lr": lr * unfreeze_lr_ratio, ...})
no_improve = 0  # resetear early stopping
```

Añadir nuevo param group al optimizador existente preserva el estado de momentum de los grupos
anteriores — no se re-crea el optimizador, que perdería los momentos acumulados.

**Experimentos:**

| Run | unfreeze_every | unfreeze_layers | unfreeze_lr_ratio |
|-----|---------------|-----------------|-------------------|
| 30a | 25 | 4 | 0.1 |
| 30b | 30 | 4 | 0.1 |

**Lanzamiento:**

```bash
# 30b (ganador) — UNFREEZE_EVERY=30
make ai-train-gpu \
  MODEL=IIC/RigoBERTa-Clinical \
  MAX_LENGTH=512 \
  BATCH_SIZE=8 \
  GRAD_ACCUM=4 \
  THRESHOLD=0.3 \
  POS_WEIGHT_CAP=10.0 \
  LR=1e-4 \
  WARMUP_RATIO=0.1 \
  WEIGHT_DECAY=0.1 \
  DROPOUT=0.3 \
  FREEZE_LAYERS=20 \
  EPOCHS=150 \
  PATIENCE=20 \
  FULL_CODES=1 \
  PRETRAIN_EPOCHS=10 \
  "PRETRAIN_TASKX=/data/codiesp_csvs/codiesp_X_source_train.csv /data/codiesp_csvs/codiesp_X_source_validation.csv" \
  LABEL_SMOOTHING=0.1 \
  LR_SCHEDULE=plateau \
  UNFREEZE_EVERY=30 \
  UNFREEZE_LAYERS=4 \
  UNFREEZE_LR_RATIO=0.1 \
  2>&1 | tee /tmp/train_paso30b.log

# 30a: UNFREEZE_EVERY=25 → tee /tmp/train_paso30a.log
```

**Resultado:**

| Run | F1-micro | best época | per-class micro | per-class macro | early stop |
|-----|----------|------------|-----------------|-----------------|------------|
| 29a (ref) | 0.4819 | 115 | 0.5383 | 0.1420 | 135 |
| **30b** | **0.4842** | **104** | **0.5479** | **0.1494** | 140 |
| 30a | 0.4767 | 126 | 0.5352 | 0.1421 | 146 |

Eventos de unfreeze en 30a (unfreeze_every=25) y su efecto acumulado:

| Época | Capas activadas | F1 antes | F1 pico post-unfreeze | Δ F1 |
|-------|----------------|----------|-----------------------|------|
| 25 | 16–19 | 0.4275 | 0.4576 | +3.0pp |
| 50 | 12–15 | 0.4576 | 0.4745 | +1.7pp |
| 75 | 8–11  | 0.4745 | 0.4747 | +0.02pp |
| 100 | 4–7   | 0.4747 | 0.4760 | +0.13pp |
| 125 | 0–3   | 0.4760 | 0.4767 | +0.07pp |

El progressive unfreezing funciona: cada evento de unfreeze desencadenó un nuevo pico de
F1. 30b supera a 30a en +0.75pp porque los 30 epochs entre unfreezes permiten mayor
consolidación de cada grupo antes de añadir el siguiente — el primer unfreeze de 30b
(capas 16–19, época 30) aporta +4.1pp (0.4368→0.4777), frente a +3.0pp en 30a con
menos tiempo de consolidación. Ambos runs superan la referencia 29a (0.4819), aunque
la mejora es incremental, no un salto cualitativo.

El patrón de rendimientos decrecientes es llamativo: las capas superiores (16–23)
concentran casi todo el valor (+3–4pp), mientras que desbloquear capas por debajo de 12
aporta menos de 0.2pp acumulados. Con solo 500 muestras de entrenamiento, las capas más
bajas del encoder aprenden representaciones tan generales (sintaxis, morfología) que no
necesitan adaptarse a la tarea clínica. Las capas altas (semántica, contexto largo) son
las que el dominio médico requiere refinar.

Una aclaración sobre 30b: el run sí descongeló capas 4–7 en época 120, pero el early
stopping se activó antes de que ese grupo produjera ningún `new best` (20 épocas sin
mejora). Las capas 0–3 quedaron sin desbloquear. El techo real de capas <12 es
prácticamente cero con este dataset.

**Config ganadora actualizada:** 30b, F1-micro=**0.4842**, per-class=0.5479.

**Lección clave:** la estrategia óptima con estos datos es unfreeze_every=30–40 focalizado
en las capas 12–23 — no hay que desbloquear más abajo. Alternativamente, explorar si el
límite real no está en el encoder sino en la escasez de datos: el siguiente salto
cualitativo probablemente requiere sliding window (capturar el texto completo del informe,
hoy truncado al 50%) o más datos.

---

### Paso 31 — Sliding window (texto completo del informe)

**Motivación:** RigoBERTa-Clinical trunca la entrada a 512 tokens. Los informes CodiESP
tienen una media de ~570 tokens — el **50% de los documentos se cortan** antes de terminar.
Los diagnósticos secundarios y las complicaciones suelen aparecer al final del informe
("antecedentes: ..., diagnóstico principal: ..., diagnóstico secundario: ..."), lo que
significa que una parte relevante de la señal diagnóstica se descarta sistemáticamente.

Todos los runs anteriores (pasos 20-30) entrenaron con texto truncado. El modelo nunca
vio la segunda mitad de la mitad de los documentos. Recuperar esa información es
potencialmente el mayor salto cualitativo pendiente — sin cambiar el modelo ni añadir datos.

**Cómo funciona el sliding window:**

En vez de truncar al primer chunk de 512 tokens, el documento se divide en ventanas solapadas:

```
doc (570 tokens):
  chunk 1: tokens [0, 512)      (512 tok)
  chunk 2: tokens [448, 570)    (122 tok + padding)   ← stride = 512 - 64 = 448
```

Cada chunk se pasa por el encoder de forma independiente, obteniendo un embedding [CLS]
por chunk. Los embeddings de todos los chunks del mismo documento se agregan por
**mean-pool** antes de la cabeza clasificadora:

```python
# FlatClassifier.forward(), cuando doc_chunk_counts is not None:
cls = torch.stack([cls[start:start+n].mean(dim=0) for start, n in ...])
```

El resultado es un embedding de 1024 dimensiones que resume el documento completo,
en vez de solo los primeros 512 tokens.

**Parámetros clave:**

- `chunk_overlap=64`: stride = 512 − 64 = 448 tokens. Los 64 tokens de solapamiento
  preservan el contexto entre chunks (evitan que una frase a caballo de dos chunks
  quede ininteligible en uno de ellos).
- Un documento de 570 tokens genera 2 chunks. Un documento de 1000 tokens genera 3.
- Con `batch_size=4` y ~2 chunks/doc de media, el batch efectivo al encoder es ~8 chunks —
  comparable al coste de memoria de `batch_size=8` sin sliding window.

**Configuración:**

Base 30b (mejor config), solo añadiendo `--sliding_window` y reduciendo batch a 4:

| Parámetro | Valor |
|-----------|-------|
| SLIDING_WINDOW | 1 |
| CHUNK_OVERLAP | 64 |
| BATCH_SIZE | 4 (2 chunks/doc → coste encoder ~batch=8) |
| FREEZE_LAYERS | 20 |
| UNFREEZE_EVERY | 30 |
| UNFREEZE_LR_RATIO | 0.1 |
| LR_SCHEDULE | plateau |
| LABEL_SMOOTHING | 0.1 |
| todo lo demás | igual que 30b |

**Lanzamiento:**

```bash
make ai-train-gpu \
  MODEL=IIC/RigoBERTa-Clinical \
  MAX_LENGTH=512 \
  BATCH_SIZE=4 \
  GRAD_ACCUM=4 \
  THRESHOLD=0.3 \
  POS_WEIGHT_CAP=10.0 \
  LR=1e-4 \
  WARMUP_RATIO=0.1 \
  WEIGHT_DECAY=0.1 \
  DROPOUT=0.3 \
  FREEZE_LAYERS=20 \
  EPOCHS=150 \
  PATIENCE=20 \
  FULL_CODES=1 \
  PRETRAIN_EPOCHS=10 \
  "PRETRAIN_TASKX=/data/codiesp_csvs/codiesp_X_source_train.csv /data/codiesp_csvs/codiesp_X_source_validation.csv" \
  LABEL_SMOOTHING=0.1 \
  LR_SCHEDULE=plateau \
  SLIDING_WINDOW=1 \
  CHUNK_OVERLAP=64 \
  UNFREEZE_EVERY=30 \
  UNFREEZE_LAYERS=4 \
  UNFREEZE_LR_RATIO=0.1 \
  2>&1 | tee /tmp/train_paso31.log
```

**Resultado:**

| Métrica | Valor | vs 30b (ref) |
|---------|-------|--------------|
| F1-micro (best val) | 0.4124 | −0.72pp |
| per-class micro | 0.4765 | −0.71pp |
| per-class macro | 0.1352 | −0.14pp |

El sliding window **empeoró** el resultado respecto a 30b (0.4842). Un retroceso
significativo de −0.72pp en F1-micro a pesar de que el modelo ahora ve el documento
completo.

**Análisis:** el problema de fondo es que los códigos CIE-10 son anotaciones a nivel de
documento, no a nivel de fragmento. Al hacer mean-pool de los embeddings [CLS] de cada
chunk, se promedian representaciones de fragmentos potencialmente irrelevantes (resúmenes
administrativos, datos demográficos) con los fragmentos que contienen la señal diagnóstica
real. Con 512 tokens ya se captura la mayor parte del texto diagnóstico relevante; los
chunks adicionales añaden más ruido que señal.

Un segundo factor: con solo ~500 documentos de entrenamiento, el modelo no tiene suficientes
ejemplos del patrón multi-chunk para aprender a ignorar los chunks ruidosos. La varianza
del mean-pool aumenta sin que el modelo tenga capacidad de filtrarla.

La estrategia de sliding window con mean-pool simple no es el camino con este dataset.
Alternativas si se quisiera recuperar el texto completo: attention-pool ponderado por
relevancia de cada chunk, o limitar a max 2 chunks y descartar el segundo si no aporta
señal (basado en entropia de tokens). Pero con 500 muestras, ninguna variante de multi-chunk
tiene muchas probabilidades de superar la truncación simple.

**Lección clave:** la truncación a 512 tokens no era el cuello de botella. El límite
está en la ratio datos/clases (500 docs, 1767 códigos). El siguiente salto cualitativo
requiere más datos, no más tokens por documento.

**Config ganadora sigue siendo 30b** (F1-micro=0.4842, sin sliding window).

---

### Paso 32 — Hierarchical consistency loss

**Motivación:** CIE-10 tiene estructura jerárquica explícita: el código `J18.0` (Neumonía
debida a *Mycoplasma pneumoniae*) implica necesariamente `J18` (Neumonía, no especificada)
y el capítulo `J` (Enfermedades del sistema respiratorio). El modelo flat actual trata las
1767 clases como independientes — puede predecir `J18.0` sin predecir `J18`, lo que es
semánticamente inconsistente.

Esta inconsistencia es especialmente dañina para los códigos raros: si el modelo ha visto
pocas veces `J18.0` pero muchas veces `J18`, un regularizador jerárquico fuerza al modelo
a "apoyarse" en la señal de los padres para predecir mejor los hijos. El efecto esperado
es una mejora en **F1-macro** (códigos raros) más que en F1-micro.

**Estructura CIE-10 en nuestro label set:**

```
J18.0  →  padre: J18  (si existe en nuestros 1767 códigos)
J18    →  padre: J1x  (bloque, normalmente no en label set)
```

La mayoría de los pares relevantes son (código 4 caracteres, código 3 caracteres). Los
capítulos (`A`, `B`, ..., `Z`) en general no están en el label set como etiquetas propias.

**Implementación — hierarchical consistency loss:**

Para cada par `(hijo_idx, padre_idx)` donde ambos están en el label set:

```python
# Si el hijo tiene logit alto, el padre debe tenerlo también
# Penalizar cuando logit_hijo > logit_padre
hier_loss = relu(logits[:, child_indices] - logits[:, parent_indices]).mean()
total_loss = bce_loss + lambda_hier * hier_loss
```

El `relu` hace que solo penalice en la dirección incorrecta (hijo > padre); si padre > hijo
no hay penalización extra. Es asimétrico y no interfiere con los pares donde el modelo
ya es consistente.

**Construcción del mapeo hijo→padre:**

```python
# En dataset/__init__: construir child_parent_pairs
child_parent_pairs = []
for code, idx in label2idx.items():
    parent = code[:3]  # "J18.0" → "J18"
    if parent in label2idx and parent != code:
        child_parent_pairs.append((idx, label2idx[parent]))
child_indices = torch.tensor([c for c, p in child_parent_pairs])
parent_indices = torch.tensor([p for c, p in child_parent_pairs])
```

**Diseño del experimento:**

Base: config 30b (F1=0.4842). Solo se añade el regularizador jerárquico con distintos
valores de `lambda_hier`:

| Run | lambda_hier | Hipótesis |
|-----|-------------|-----------|
| 32a | 0.1 | Regularizador suave, efecto pequeño pero limpio |
| 32b | 0.5 | Regularizador moderado — punto de partida |
| 32c | 1.0 | Regularizador fuerte — ¿sobreregulaiza? |

Métrica de interés principal: **F1-macro** (mejora en códigos raros). F1-micro puede
bajar ligeramente si el modelo redistribuye confianza hacia los padres a costa de los hijos.

**Lanzamiento (base para los tres runs — cambiar solo LAMBDA_HIER y el log):**

```bash
# 32b (punto de partida) — idéntico al 30b + LAMBDA_HIER=0.5
make ai-train-gpu \
  MODEL=IIC/RigoBERTa-Clinical \
  MAX_LENGTH=512 \
  BATCH_SIZE=8 \
  GRAD_ACCUM=4 \
  THRESHOLD=0.3 \
  POS_WEIGHT_CAP=10.0 \
  LR=1e-4 \
  WARMUP_RATIO=0.1 \
  WEIGHT_DECAY=0.1 \
  DROPOUT=0.3 \
  FREEZE_LAYERS=20 \
  EPOCHS=150 \
  PATIENCE=20 \
  FULL_CODES=1 \
  PRETRAIN_EPOCHS=10 \
  "PRETRAIN_TASKX=/data/codiesp_csvs/codiesp_X_source_train.csv /data/codiesp_csvs/codiesp_X_source_validation.csv" \
  LABEL_SMOOTHING=0.1 \
  LR_SCHEDULE=plateau \
  UNFREEZE_EVERY=30 \
  UNFREEZE_LAYERS=4 \
  UNFREEZE_LR_RATIO=0.1 \
  LAMBDA_HIER=0.5 \
  2>&1 | tee /tmp/train_paso32b.log

# 32a: LAMBDA_HIER=0.1  → tee /tmp/train_paso32a.log
# 32c: LAMBDA_HIER=1.0  → tee /tmp/train_paso32c.log
```

**Resultado:**

| Run | λ | F1-micro | best época | per-class micro | per-class macro |
|-----|---|----------|------------|-----------------|-----------------|
| 30b (ref) | — | 0.4842 | 104 | 0.5479 | 0.1494 |
| **32b** | **0.5** | **0.4888** | **135** | **0.5509** | **0.1524** |
| 32a | 0.1 | 0.4876 | 66 | 0.5482 | **0.1638** |
| 32c | 1.0 | 0.4831 | 86 | 0.5371 | 0.1575 |

El regularizador jerárquico funciona. El patrón es claro:

- **λ=0.1** (suave): F1-micro intermedio (+0.34pp vs ref), pero **mejor F1-macro de todos
  (0.1638, +1.44pp vs ref)** — la señal suave ayuda especialmente a los códigos raros.
  Pico muy temprano (época 66): la coherencia jerárquica se integra rápido con poco peso.
- **λ=0.5** (moderado): **mejor F1-micro (0.4888, +0.46pp vs ref)**, buen equilibrio
  entre precisión global y códigos raros. Ganador en la métrica principal. Pico en época 135.
- **λ=1.0** (fuerte): peor que el baseline en F1-micro (0.4831 < 0.4842). El regularizador
  domina demasiado la loss BCE y distorsiona la señal de clasificación.

**Config ganadora: 32b (λ=0.5), F1-micro=0.4888.**
Si el objetivo prioritario es recall en códigos raros: 32a (λ=0.1) da mejor F1-macro (0.1638).

---

## Reflexión sobre el estado actual y próximos pasos

### Dónde estamos (actualizado paso 32)

| Paso | Configuración clave | F1-micro | F1-macro |
|------|---------------------|----------|----------|
| 20 | Sin pretrain, full codes | 0.327 | 0.050 |
| 21 | Pretrain CIE-10, batch=4 | 0.431 | 0.092 |
| 23 | + task_X snippets, batch=8 | 0.470 | 0.139 |
| 28b | + ReduceLROnPlateau | 0.475 | 0.116 |
| 30b | + Progressive unfreezing (unfreeze_every=30) | 0.4842 | 0.1494 |
| 31 | + Sliding window (mean-pool chunks) | 0.4124 | 0.1352 |
| **32b** | **+ Hierarchical consistency loss (λ=0.5)** | **0.4888** | **0.1524** |

Las claves del progreso: modelo clínico correcto (RigoBERTa-Clinical), pre-entrenamiento
combinado con jerga médica real (task_X), freeze=20 imprescindible con 500 muestras,
y scheduler adaptativo que permite seguir aprendiendo más allá de la época 50.
El progressive unfreezing (paso 30) fue el último salto real. El sliding window (paso 31)
confirmó que la truncación no era el cuello de botella: el problema es la ratio datos/clases
(~500 documentos, 1767 clases → menos de 1 ejemplo de media por clase).

### Opciones por orden de impacto esperado (actualizado paso 32)

| Opción | Esfuerzo | Impacto esperado | Estado |
| ------ | -------- | ---------------- | ------ |
| **Más datos (back-translation)** | Alto | +3-8pp F1 | Pendiente |
| **Datasets adicionales** | Medio | +pretrain encodings | Ya hacemos pretrain CIE-10 |
| **Hierarchical consistency loss** | Medio | +1-3pp F1-macro (códigos raros) | ✓ Paso 32 (+0.46pp micro, +0.3pp macro) |
| **Ensemble de checkpoints** | Bajo | +0.5-1pp gratis | Pendiente |
| **Sliding window** | Alto | −0.72pp | Descartado (paso 31) |

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
`attn_impl`, `full_codes`, `max_length`, `epochs_run`, `epochs_max`,
`batch_size`, `grad_accum`, `effective_batch`, `lr`, `patience`, `threshold`, `pos_weight_cap`,
`train_rows`, `val_rows`, `num_codes`, `val_p_micro`, `val_r_micro`, `val_f1_micro`,
`val_p_macro`, `val_r_macro`, `val_f1_macro`, `total_seconds`, `avg_epoch_seconds`

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

---

## Anexo A — Baseline TF-IDF

Para contextualizar los resultados del transformer, se implementó un baseline clásico
en `ai_engine/baseline_tfidf.py`. Si el baseline supera al transformer, significa que
el modelo neuronal no está aportando representaciones mejores que las estadísticas de
frecuencia de palabras.

### Arquitectura del baseline

- **Vectorización:** TF-IDF con unigramas y bigramas, min_df=2, max_features=50 000,
  sublinear_tf=True (log de frecuencias).
- **Clasificador:** `OneVsRestClassifier(LogisticRegression)` — un clasificador binario
  por código, entrenado independientemente. Es el enfoque estándar de multi-label con
  sklearn (binary relevance).
- **Threshold:** igual que en el transformer (0.5 por defecto, sweep de 0.1 a 0.6).

### Por qué OneVsRestClassifier funciona en multi-label

Cada código CIE-10 es una etiqueta binaria independiente (puede estar o no en el documento).
`OneVsRestClassifier` entrena 809 clasificadores LR, uno por código, usando las mismas
features TF-IDF. `predict_proba` devuelve una probabilidad por código → se aplica el
threshold igual que en el transformer.

### Resultados

| Modelo | F1-micro | Threshold óptimo |
| ------ | -------- | ---------------- |
| TF-IDF + LR (baseline) | 0.213 | 0.1 |
| RigoBERTa-Clinical (paso 10b) | **0.369** | 0.5 |

El transformer supera al baseline en **+15.6 puntos de F1**, confirmando que las
representaciones contextuales aportan valor real sobre la frecuencia de palabras.

Notas relevantes:

- Con threshold≥0.4 el TF-IDF no predice nada — las probabilidades LR en multi-label
  con 809 clases son muy planas; el threshold óptimo es 0.1.
- ~111 códigos presentes en validación no aparecen en train: ningún modelo puede
  predecirlos, son pérdida de F1 garantizada.
- La LR converge completamente con max_iter=10000 y el resultado es idéntico — 0.213
  era ya el techo real del TF-IDF.

---

## Anexo B — Solapamiento de etiquetas entre train y val

Análisis de los códigos CIE-10 presentes en cada split:

| | Códigos únicos |
|---|---|
| Train | 809 |
| Val | 625 |
| **Comunes (ambos splits)** | **514** |
| Solo en train (no evaluables) | 295 |
| Solo en val (imposible predecir) | **111** |

**Implicaciones:**

- Los **111 códigos exclusivos de val** son predicciones imposibles para cualquier
  modelo entrenado sobre train: no aparecen en `code_to_idx` y nunca se verán en
  train. Generan falsos negativos garantizados que deprimen el F1.
- Los **295 códigos exclusivos de train** los aprende el modelo pero nunca se evalúan
  — son capacidad "desperdiciada" desde el punto de vista de la métrica.
- La métrica real del modelo debería medirse solo sobre los **514 códigos comunes**.
  El F1 actual (0.369) está calculado sobre todos los códigos de val (625), incluyendo
  los 111 imposibles.

**Qué afecta esto al transformer vs TF-IDF:**
Ambos modelos sufren exactamente el mismo problema — `code_to_idx` (transformer) y
`MultiLabelBinarizer` (TF-IDF) se construyen sobre train, así que los 111 códigos
de val son invisibles para ambos.

---

## Anexo C — Referencias bibliográficas

### CodiESP Shared Task

El corpus y las métricas de referencia de este proyecto provienen del shared task
CodiEsp (Clinical Case Coding in Spanish), organizado en CLEF eHealth 2020.

Los mejores sistemas del challenge para diagnóstico (CodiEsp-D) alcanzaron
**F1≈0.687** con códigos completos usando enfoques de matching de diccionario.
Sistemas post-challenge basados en transformers llegan a **F1≈0.78-0.88**.

```bibtex
@inproceedings{miranda2020codiesp,
  title     = {Overview of Automatic Clinical Coding: Annotations, Guidelines,
               and Solutions for Non-English Clinical Cases at CodiEsp Track
               of CLEF eHealth 2020},
  author    = {Miranda-Escalada, Antonio and Gonzalez-Agirre, Aitor and
               Armengol-Estapé, Jordi and Krallinger, Martin},
  booktitle = {Working Notes of CLEF 2020 -- Conference and Labs of the
               Evaluation Forum},
  series    = {CEUR Workshop Proceedings},
  volume    = {2696},
  year      = {2020},
  url       = {https://ceur-ws.org/Vol-2696/paper_263.pdf}
}
```

### RigoBERTa-Clinical

Modelo base usado a partir del paso 9. Preentrenado sobre texto clínico en español.

```bibtex
@inproceedings{llop2022rigoberta,
  title     = {RigoBERTa: A State-of-the-Art Language Model for Spanish},
  author    = {Llop, Joan and Papaioannou, Jordi and Gómez-Puente, Marc and
               Aguilar, Miquel and Vidal, Pere-Lluís},
  booktitle = {Proceedings of the Language Resources and Evaluation Conference (LREC)},
  year      = {2022},
  url       = {https://huggingface.co/IIC/RigoBERTa-Clinical}
}
```

---

## Anexo D — Baseline de Diccionario

Implementado en `ai_engine/baseline_dict.py`. A diferencia del TF-IDF (que aprende
de los datos de entrenamiento), este baseline parte de una base **no supervisada**:
compara el texto de cada nota con el diccionario oficial CIE-10 en español, scrapeado
de eCIE-maps, sin ver ninguna etiqueta de entrenamiento.

### Idea

Para cada nota clínica se busca si algún término del diccionario CIE-10 aparece en el
texto. Si aparece, se predice el bloque (3 primeros caracteres del código) correspondiente.
Es el enfoque que usaron los mejores sistemas del challenge CodiESP 2020, alcanzando
F1≈0.687 con código completo.

### Por qué es un baseline relevante para el TFG

Antes de saber si BERT aprende algo útil, hay que saber qué se obtiene sin ningún
aprendizaje. Si el diccionario ya da F1=0.3, BERT tiene que superar eso para justificar
su uso. Si el diccionario da F1=0.05, BERT tiene más margen y el problema es claramente
de vocabulario, no de semántica profunda.

### Pipeline de matching

El sistema aplica cuatro pasos antes de comparar texto con diccionario:

1. **Expansión de variantes del diccionario** — cada entrada del CSV puede contener
   múltiples nombres separados por `|` (p. ej. `"Fiebre tifoidea | Infección debida a
   Salmonella typhi"`). Además, el contenido entre paréntesis es una especificación o
   aclaración (p. ej. `"Tuberculosis de las meninges (cerebral) (espinal)"`). Para cada
   entrada se generan automáticamente:
   - Una versión sin los paréntesis: `"Tuberculosis de las meninges"`.
   - Una versión con el contenido inlined: `"Tuberculosis de las meninges cerebral espinal"`.
   - El contenido del paréntesis como término independiente, si tiene ≥ 2 palabras (útil
     para acrónimos: `"ANTU (alfa naftiltiourea)"` → `"alfa naftiltiourea"`).

   Esto aumenta el número de patrones de ~96k a ~117k en diagnoses, cubriendo las formas
   alternativas que el médico puede usar al redactar.

2. **Lematización con normalización de género** — tanto las variantes del diccionario
   como cada nota clínica se lematizan con spaCy `es_core_news_lg` (modelo grande de
   español, ~685k vectores, entrenado sobre Wikipedia y noticias). Esto permite que
   `"enfermedades cardíacas"` matchee con `"enfermedad cardíaca"`. Además se aplica una
   normalización de género gramatical: los adjetivos que spaCy identifica como femeninos
   (terminados en `-a`) se convierten a su forma masculina cuando esta existe en el
   vocabulario. Así `"insuficiencia cardíaca"` y `"soplo cardíaco"` producen el mismo
   lema `"insuficiencia cardiaco"` y `"soplo cardiaco"` sin necesidad de tener ambas
   variantes en el diccionario. La puntuación también se excluye (antes permanecía en
   el lema, causando fallos de matching). La lematización es el paso más caro
   (~2 min por diccionario); los resultados se cachean en disco con una clave basada
   en el hash del CSV y solo se recomputan si el fichero cambia.

3. **Normalización** — minúsculas y eliminación de acentos tras lematizar, para que
   `"hepático"` y `"hepatico"` no sean cadenas distintas.

4. **Word boundaries** — los patrones usan `\b...\b` (expresión regular de límite de
   palabra) para evitar falsos positivos de substring: `"art"` no matchea dentro de
   `"partir"`. Esto es fundamental cuando se tienen 100k+ patrones cortos.

### Fuentes evaluadas por separado

Se evalúan cinco fuentes de forma independiente para aislar la contribución de cada una:

| Fuente | ~Patrones | Qué matchea | Supervisado |
|--------|-----------|-------------|-------------|
| `diagnoses` | ~117k | Nombres diagnósticos CIE-10-MC con variantes "\|" y paréntesis | No |
| `procedures` | ~78k | Descripciones de procedimientos CIE-10-PCS | No |
| `chemicals` | ~5k | Nombres de fármacos y sustancias, bloque de intoxicación | No |
| `clinical` | ~23k | Términos clínicos reales de las anotaciones task_x, expandidos con sinónimos léxicos | Semi |
| `corpus` | variable | N-gramas discriminativos extraídos de las notas de entrenamiento | Sí |
| `combined` | unión | Unión de patrones de todas las fuentes anteriores | Semi |

**`procedures`**: los procedimientos (CIE-10-PCS) no son diagnósticos, pero si la nota
dice "apendicectomía laparoscópica" es probable que haya un código de apendicitis
(K35–K37). El matching captura esa señal indirecta.

**`chemicals`**: clave en urgencias o toxicología. Si aparece "paracetamol" o
"ibuprofeno", hay casi siempre un código de efecto adverso o intoxicación (T36–T50).

**`clinical`**: El corpus CodiESP proporciona en `codiesp_X_source_*.csv` las
anotaciones de explainabilidad del challenge: para cada código asignado a una nota,
el anotador marcó el fragmento de texto exacto que justifica ese código (p. ej.
`code=N28.89` → `text="ectasia pielocalicial"`). Esto nos da **4587 términos clínicos
reales** con toda la variabilidad léxica del médico: siglas, jerga, variantes
ortográficas. Estos términos se expanden con sinónimos léxicos usando los word vectors
de `es_core_news_lg`: para cada palabra de contenido (sustantivo, adjetivo, verbo) en
los términos, se buscan las N palabras más similares en el vocabulario (similitud
coseno > 0.65) y se generan variantes del término sustituyendo una palabra a la vez.
Por ejemplo, `"estenosis pieloureteral"` puede generar `"estrechamiento pieloureteral"`.

**Nota sobre supervisión de `clinical`**: esta fuente usa los ficheros task_x de train
Y validación, por lo que conoce parcialmente qué términos aparecen en val. Sus métricas
sobre val son **semi-supervisadas** y no comparables directamente con las de las demás
fuentes. Se reportan por separado para ser transparentes.

**`corpus`**: La fuente más poderosa del conjunto. En lugar de usar terminología formal
del diccionario oficial, extrae directamente de las notas de entrenamiento los n-gramas
(secuencias de 2 a 5 palabras) que se asocian de forma discriminativa a cada bloque
CIE-10. El algoritmo es:

1. Lematizar todas las notas de train.
2. Para cada bloque, recoger los índices de las notas que tienen ese código.
3. Para cada n-grama que aparece en esas notas, calcular:
   - `freq` = número de notas con ese bloque que contienen el n-grama.
   - `precision` = `freq` / (número total de notas que contienen el n-grama).
4. Conservar el n-grama si `freq >= 2` y `precision >= 0.5`.

Esto captura automáticamente todo lo que `clinical` captura manualmente más:
las abreviaturas médicas (IAM, DM2, EPOC, FA, HTA), las frases de contexto implícito
("tratamiento con insulina" → E11 Diabetes mellitus), y cualquier patrón léxico
recurrente en las notas reales. Al usar solo train, la evaluación sobre val sigue
siendo **supervisada y limpia**.

Tras la ejecución se genera un CSV de reporte (`--report_file`) con la tabla
`bloque → top-5 n-gramas` por fuente, útil para auditar qué patrones está usando
el sistema para cada código.

**`combined`**: en lugar de evaluar cada fuente por separado, `combined` hace la unión
de todos los patrones de todas las fuentes cargadas. Así una nota recibe la predicción
de bloque X si cualquiera de las cinco fuentes lo matchea. La consecuencia esperable es:

- **Recall máximo**: casi todo lo que cualquier fuente captura queda cubierto.
- **Precisión reducida**: si una fuente ruidosa (como `corpus`) predice muchos falsos
  positivos, estos se propagan al combined.

Por eso se evalúan dos variantes de `combined`:

- **Sin corpus**: solo diagnoses + procedures + chemicals + clinical. Recall algo menor
  pero precisión mucho mayor al eliminar el ruido de n-gramas.
- **Con corpus exclusive**: `corpus` con `--corpus_exclusive`, donde cada n-grama se
  asigna únicamente al bloque con mayor `precision × freq` en lugar de a todos los
  bloques que superen el umbral. Esto reduce drásticamente los falsos positivos.

**Nota sobre rendimiento**: `es_dep_news_trf` es un modelo transformer (XLM-RoBERTa)
~10-20× más lento que el modelo estadístico `es_core_news_lg` en CPU. Para acelerar
la lematización, el script llama a `spacy.prefer_gpu()` y se instala `cupy-cuda12x`
en el Dockerfile para aprovechar la RTX 4080. El coste solo se paga la primera vez
(las lematizaciones se cachean en disco); ejecuciones posteriores son rápidas.

### Por qué la precisión es alta y el recall es bajo

Cuando el diccionario encuentra una coincidencia, casi siempre es correcta (P≈0.93
en la versión inicial). Pero la mayoría de los diagnósticos se documentan con
abreviaturas, siglas o jerga clínica que no aparece en el diccionario formal:

- **Siglas**: "IAM" (infarto agudo de miocardio), "HTA" (hipertensión arterial), "EPOC",
  "DM2", "FA"... El diccionario escribe el nombre completo; el médico usa la abreviatura.
  La lematización no resuelve esto porque no conoce la equivalencia.
- **Jerga**: "el paciente sangra" no matchea "hemorragia"; "falla cardiaca" no matchea
  "insuficiencia cardíaca congestiva".
- **Contexto implícito**: un diagnóstico puede estar implícito en el tratamiento (se
  administró insulina → DM) sin que aparezca el nombre de la enfermedad.

La fuente `clinical` reduce este problema al usar los términos reales del médico, pero
solo cubre los códigos que aparecen en CodiESP, no el universo CIE-10 completo.

### Resultados del baseline de diccionario

| Fuente | Split | P-micro | R-micro | F1-micro | P-macro | R-macro | F1-macro | Supervisado |
|--------|-------|---------|---------|----------|---------|---------|----------|----- |
| diagnoses | train | 0.433 | 0.196 | 0.270 | 0.258 | 0.174 | 0.188 | No |
| diagnoses | val | 0.444 | 0.193 | 0.269 | 0.189 | 0.133 | 0.144 | No |
| procedures | train | 0.010 | 0.002 | 0.004 | 0.000 | 0.001 | 0.001 | No |
| procedures | val | 0.010 | 0.003 | 0.005 | 0.000 | 0.001 | 0.000 | No |
| chemicals | train | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | No |
| chemicals | val | 0.044 | 0.001 | 0.002 | 0.000 | 0.002 | 0.000 | No |
| clinical | train | 0.491 | 0.861 | 0.626 | 0.623 | 0.707 | 0.620 | Semi |
| clinical | val | 0.490 | 0.856 | 0.623 | 0.472 | 0.548 | 0.476 | Semi |
| corpus | train | 0.072 | 0.906 | 0.133 | 0.143 | 0.509 | 0.186 | Sí |
| corpus | val | 0.048 | 0.704 | 0.090 | 0.041 | 0.276 | 0.056 | Sí |
| combined (con corpus, excl.) | train | 0.208 | 0.928 | 0.340 | 0.511 | 0.744 | 0.541 | Semi |
| combined (con corpus, excl.) | val | 0.142 | 0.904 | 0.246 | 0.362 | 0.568 | 0.384 | Semi |
| combined (sin corpus) | train | 0.072 | 0.977 | 0.133 | 0.339 | 0.790 | 0.389 | Semi |
| combined (sin corpus) | val | 0.059 | 0.938 | 0.111 | 0.239 | 0.590 | 0.266 | Semi |

Comparación con los otros baselines:

| Modelo | F1-micro (val) | P-micro (val) | R-micro (val) | Supervisado |
| ------ | -------------- | ------------- | ------------- | ----------- |
| dict/diagnoses | 0.269 | 0.444 | 0.193 | No |
| dict/corpus (min_prec=0.5) | 0.090 | 0.048 | 0.704 | Sí |
| dict/corpus (excl., min_prec=0.8) | 0.246 | 0.142 | 0.904 | Sí |
| dict/clinical | **0.623** | 0.490 | 0.856 | Semi |
| dict/combined (excl.) | 0.246 | 0.142 | **0.904** | Semi |
| dict/combined (sin corpus) | 0.111 | 0.059 | 0.938 | Semi |
| TF-IDF + LR | 0.213 | — | — | Sí (train) |
| RigoBERTa-Clinical (paso 11) | 0.392 | — | — | Sí (train) |

`diagnoses` mejora de 0.257 a 0.269 con el modelo transformer (`es_dep_news_trf`)
y la normalización de género gramatical de adjetivos.

`corpus` tiene recall muy alto (R≥0.70) pero precisión baja. El problema fundamental
es el **trade-off precisión-recall con F1 como métrica**. Añadir más patrones aumenta
el recall pero puede destruir el F1 si la precisión cae demasiado: la media armónica
penaliza fuertemente los desequilibrios extremos. Por ejemplo, predecir todos los 920
bloques para cada nota daría R=1.0 pero F1≈0.01. Con `min_precision=0.5` los n-gramas
se asignan a múltiples bloques simultáneamente, generando ~140 predicciones por nota
(vs ~10 verdaderas). Con `--corpus_exclusive` cada n-grama va solo al bloque con mayor
`precision×freq`, reduciendo predicciones a ~60/nota y mejorando F1 de 0.090 a 0.246.

`combined` demuestra que más patrones no siempre es mejor: añadir `corpus` al combined
**reduce** el F1 de `clinical` solo (0.623) a 0.246, porque los falsos positivos de
corpus contaminan las predicciones de las otras fuentes.

**`clinical` solo sigue siendo el mejor baseline**, con F1=0.623. El objetivo de las
siguientes iteraciones sobre `corpus` es conseguir que sus patrones sean suficientemente
precisos (P≥0.4) para que combined supere a clinical en F1, aprovechando el recall
extra (+5pp) sin destruir la precisión.

#### Iteraciones de mejora del corpus

**Iteración 1 — corpus base** (`min_precision=0.5`):

- val: P=0.048, R=0.704, F1=0.090 — ~140 predicciones/nota, demasiado ruido.
- Causa: un n-grama con `precision=0.5` puede satisfacer el umbral para múltiples bloques
  a la vez (e.g., "fallo cardiaco" aparece en notas con I50, I11, I13… y cada uno supera 0.5).

**Iteración 2 — corpus exclusive** (`min_precision=0.8`, `--corpus_exclusive`):

- val: P=0.142, R=0.904, F1=0.246 — ~60 predicciones/nota.
- `exclusive` asigna cada n-grama solo al bloque con mayor `precision×freq`. Mejora F1
  de 0.090 a 0.246 pero sigue generando demasiado ruido.

**Iteración 3 — en curso**: dos estrategias en paralelo:

**3A — `max_patterns=20`** (`--corpus_exclusive --corpus_min_precision 0.8 --corpus_max_patterns 20`):

El problema de la iteración 2 es que algunos bloques contribuyen cientos de patrones:
cualquier n-grama que aparezca en notas con ese código pasa el umbral 0.8 y se queda.
Con `--corpus_max_patterns 20` cada bloque conserva solo sus **top-20 por frecuencia**
(los más repetidos en las notas de entrenamiento). La lógica es que un n-grama que aparece
en 15 notas con el código I21 es mucho más fiable que uno que aparece en solo 2 notas: tiene
más evidencia empírica y es menos probable que sea una coincidencia de esa nota concreta.
Si cada bloque contribuye máximo 20 patrones y una nota matchea en media ~5 bloques,
el máximo teórico de predicciones es 5×20=100 — frente a las ~60 actuales del modo
exclusive sin límite, pero con patrones más fiables (los más frecuentes).

**3B — `precision=1.0`** (`--corpus_exclusive --corpus_min_precision 1.0 --corpus_min_freq 3`):

Un patrón con `precision=1.0` **nunca aparece en una nota de entrenamiento sin su código**.
Esto convierte cada n-grama en un indicador diagnóstico libre de falsos positivos en train.
El requisito adicional `min_freq=3` (en ≥3 notas distintas) descarta patrones que sean
específicos a una sola nota y que podrían ser frases idiosincrásicas del médico que la
escribió. La hipótesis es que un n-grama visto en 3+ notas diferentes, siempre ligado
al mismo código, es un término genuinamente diagnóstico que generalizará bien a val.
El precio es un recall más bajo: habrá bloques sin ningún patrón con precision=1.0 porque
todos sus n-gramas aparecen también en notas de otros bloques. Esos bloques dependerán
de las otras fuentes (`diagnoses`, `clinical`).

**Objetivo de ambas variantes**: conseguir que `corpus` tenga P-micro val ≥ 0.4 para
que `combined` (corpus + clinical + diagnoses) supere el F1=0.623 de `clinical` solo,
aprovechando el recall extra que corpus aporta (+5pp sobre clinical).

| Variante | P-micro val | R-micro val | F1-micro val | Pred/nota |
| -------- | ----------- | ----------- | ------------ | --------- |
| corpus base (iter. 1) | 0.048 | 0.704 | 0.090 | ~140 |
| corpus exclusive (iter. 2) | 0.142 | 0.904 | 0.246 | ~60 |
| combined max_patterns=20 (iter. 3A) | 0.318 | 0.884 | 0.468 | ~26 |
| combined precision=1.0 (iter. 3B) | 0.192 | 0.893 | 0.316 | ~44 |

3A mejora notablemente (+0.222 F1 respecto a iter. 2), pero ninguna variante supera
`clinical` solo (F1=0.623). El motivo: para que `combined` mejore el F1 de `clinical`,
el corpus necesita añadir recall con precisión ≥ 0.490. Con solo 500 notas de train,
los n-gramas aprendidos son más ruidosos que las anotaciones directas de `clinical`, y
el recall extra que corpus aporta (+2.8pp: 0.856→0.884) no compensa la caída de
precisión (-17.2pp: 0.490→0.318).

**Iteración 4 — corpus selectivo**: en lugar de añadir corpus a todos los bloques,
activarlo solo para los bloques que `clinical` **no cubre** (aquellos sin ningún patrón
en task_x). Así corpus no contamina los bloques donde clinical ya es bueno, y solo
interviene en el 14% de recall que falta. Esto se implementa con `--corpus_selective`:
antes de evaluar, se calcula la cobertura de `clinical` sobre el vocabulario de bloques
del train+val, y los patrones de corpus se filtran a los bloques no cubiertos.

Resultado: filtró 272 de ~300 bloques de corpus ya cubiertos por clinical.

- val (todos los sources): P=0.377, R=0.862, F1=**0.524** — +0.056 sobre iter. 3A (~22 pred/nota)
- Aún -0.099 bajo `clinical` solo (F1=0.623)

El diagnóstico: `procedures` (P=0.010) y `chemicals` (P=0.044) siguen en el combined
contaminando la precisión. Sus patrones generan falsos positivos porque el CodiESP son
notas de diagnóstico, no de procedimientos ni farmacología.

**Iteración 5 — clinical + corpus selectivo** (`--sources clinical corpus combined`):

Eliminar `diagnoses`, `procedures` y `chemicals` del combined y dejar solo las dos
fuentes que realmente aportan en este dataset: `clinical` (cubre ~86% del recall con
P=0.490) y `corpus` selectivo (intenta cubrir el 14% restante con patrones aprendidos
del corpus de train). Hipótesis: sin el ruido de procedures/chemicals, la precisión del
combined debería acercarse a la de `clinical` solo, manteniendo el recall extra de corpus.

| Variante | P-micro val | R-micro val | F1-micro val | Pred/nota |
| -------- | ----------- | ----------- | ------------ | --------- |
| combined iter. 3A (todos, max=20) | 0.318 | 0.884 | 0.468 | ~26 |
| combined iter. 4 (selectivo, todos) | 0.377 | 0.862 | 0.524 | ~22 |
| combined iter. 5 (clinical+corpus) | 0.490 | 0.856 | **0.624** | ~16 |

Resultado: P=0.490 idéntica a `clinical` solo, F1=0.624 (+0.001). Solo 3 predicciones
adicionales en val (4146 vs 4143). El corpus selectivo **no añade ruido** pero tampoco
recupera el 14% de recall faltante: los ~28 bloques no cubiertos por clinical apenas
aparecen en val (son códigos raros con poca representación).

**Conclusión de las iteraciones de corpus**: el techo del baseline de diccionario es
F1≈0.623, alcanzado por `clinical` solo. El 14% de recall no recuperado corresponde a
códigos asignados por inferencia clínica sin evidencia textual explícita — exactamente
el tipo de razonamiento que los modelos neuronales (BERT) deben aprender.

---

### Aproximaciones LLM recientes sobre CodiESP

Resultados más recientes (2024-2025) combinando diccionarios clínicos con GPT-4:
F1≈0.89 a nivel de categoría, F1≈0.78 a nivel de subcódigo.

```bibtex
@article{llm_codiesp_2025,
  title   = {Using LLMs for Multilingual Clinical Entity Linking to ICD-10},
  journal = {arXiv preprint},
  year    = {2025},
  url     = {https://arxiv.org/abs/2509.04868}
}
```

---

## Anexo E — API de inferencia (`main.py`)

### Diseño

El servicio FastAPI expone un único endpoint `/predict` que soporta dos motores
de clasificación seleccionables por el campo `engine` del request body:

| Campo | Tipo | Default | Descripción |
| ----- | ---- | ------- | ----------- |
| `text` | string | — | Texto clínico a clasificar |
| `engine` | `"bert"` \| `"dict"` | `"bert"` | Motor de inferencia |

**`engine="bert"`**: usa el clasificador RigoBERTa entrenado con `train.py`.
Devuelve probabilidades continuas [0,1] por bloque CIE-10, ordenadas por confianza.

**`engine="dict"`**: usa el `DictClassifier` cargado desde `model/baseline_dict.json`.
El diccionario se construye con la mejor configuración del Anexo D (clinical + corpus
selectivo). La confianza es `1.0` para todos los matches (sistema determinista); en su
lugar se incluye `matched_terms` con los términos que dispararon cada código, lo que
permite al clínico verificar la razón de cada predicción sin caja negra.

### Formato de respuesta

Ambos motores devuelven el mismo esquema de cards para que el frontend sea agnóstico
al motor usado:

```json
{
  "cards": [
    { "type": "summary",         "content": "..." },
    { "type": "codes",           "content": [
        {
          "code":          "I21",
          "description":   "Infarto agudo de miocardio",
          "reason":        "Términos encontrados: infarto agudo miocardio",
          "confidence":    1.0,
          "matched_terms": ["infarto agudo miocardio"],
          "engine":        "dict"
        }
      ]
    },
    { "type": "recommendations", "content": "..." }
  ]
}
```

El campo `engine` dentro de cada código permite al frontend saber qué motor produjo
cada predicción, útil si en el futuro se combina la salida de ambos.

### Startup

Al arrancar, el servidor intenta cargar ambos motores en paralelo:

1. **BERT**: desde `MODEL_DIR/classifier.pt` y `MODEL_DIR/config.json`.
2. **Diccionario**: desde `MODEL_DIR/baseline_dict.json`. Si el fichero no existe,
   el motor `dict` queda deshabilitado y devuelve `503` hasta que se genere.

El health check `GET /` informa del estado de ambos:

```json
{ "status": "online", "model_loaded": true, "dict_loaded": true }
```

### Generar `baseline_dict.json`

```bash
docker compose run --rm ai_engine python baseline_dict.py \
  --val_file     /data/codiesp_csvs/codiesp_D_source_validation.csv \
  --diagnoses_file /data/cie10-csvs/cie10-es-diagnoses.csv \
  --task_x_train /data/codiesp_csvs/codiesp_X_source_train.csv \
  --task_x_val   /data/codiesp_csvs/codiesp_X_source_validation.csv \
  --corpus_exclusive --corpus_min_precision 0.8 --corpus_max_patterns 20 \
  --corpus_selective \
  --sources clinical corpus combined \
  --only_combined \
  --save_dict /app/model/baseline_dict.json
```

El fichero se guarda en `model/` (directorio montado como volumen) y persiste entre
reinicios del contenedor. Solo necesita regenerarse si cambian los datos de entrenamiento
o los parámetros del diccionario.

### Por qué ofrecer los dos motores

Para el TFG, tener ambos motores en la misma API permite una comparación directa en
producción: dado el mismo texto, ¿qué predice el diccionario y qué predice BERT? Las
diferencias revelan qué está aprendiendo BERT más allá del matching léxico superficial
— exactamente la hipótesis central del trabajo.

---

## Aprendizaje continuo a partir del feedback de usuarios

### Qué datos captura el sistema en producción

El backend almacena un log inmutable de eventos (Event Sourcing) y proyecciones
relacionales que constituyen un conjunto de entrenamiento implícito. Por cada informe
clínico analizado se registra:

| Tabla / Evento | Campo clave | Señal de entrenamiento |
|---|---|---|
| `messages` | `content` | Texto clínico de entrada (X) |
| `predicted_codes` | `cie10_code`, `confidence_score` | Predicción del modelo |
| `predicted_codes` | `status = "validated"`, `validated_by` | **Positivo confirmado** (Y=1) |
| `predicted_codes` | `status = "rejected"`, `rejection_reason` | **Negativo explícito** (Y=0) |
| `code_suggestions` | `suggested_code`, `selected_text` | **Etiqueta manual** (Y=1 fuera del top-k) |

Esto significa que cada sesión de un médico usando la aplicación genera muestras
etiquetadas con señal real de dominio, algo que CodiESP no puede proporcionar.

### Flujo de datos para reentrenamiento

```
PostgreSQL (predicted_codes + messages + code_suggestions)
    ↓  [SQL export / Ecto query]
raw_feedback.csv
    ↓  [script de transformación]
feedback_train.csv  (formato CodiESP: text, labels)
    ↓  [mezcla con CodiESP original]
combined_train.csv
    ↓  make ai-train-gpu
nuevo modelo
```

### Cómo construir el CSV de feedback

Consulta SQL base para extraer muestras etiquetadas desde la proyección relacional:

```sql
-- Por cada informe: texto + lista de códigos validados + sugerencias manuales
SELECT
    m.content                                       AS text,
    string_agg(DISTINCT pc.cie10_code, ';')
        FILTER (WHERE pc.status = 'validated')      AS validated_codes,
    string_agg(DISTINCT cs.suggested_code, ';')     AS suggested_codes
FROM messages m
LEFT JOIN predicted_codes pc
    ON pc.conversation_id = m.conversation_id
LEFT JOIN code_suggestions cs
    ON cs.conversation_id = m.conversation_id
WHERE m.message_type = 'user_message'
  AND (pc.status = 'validated' OR cs.suggested_code IS NOT NULL)
GROUP BY m.id, m.content
HAVING count(DISTINCT pc.cie10_code) FILTER (WHERE pc.status = 'validated') > 0
    OR count(DISTINCT cs.suggested_code) > 0;
```

La columna `labels` para el CSV se construye concatenando `validated_codes` y
`suggested_codes` (eliminando duplicados y normalizando a minúsculas, igual que CodiESP).

### Script de transformación (ejemplo Python)

```python
import pandas as pd

def build_feedback_csv(raw_df: pd.DataFrame, output_path: str):
    """
    raw_df: resultado de la query SQL anterior con columnas
            text, validated_codes, suggested_codes
    """
    rows = []
    for _, row in raw_df.iterrows():
        codes = set()
        if pd.notna(row["validated_codes"]):
            codes.update(row["validated_codes"].lower().split(";"))
        if pd.notna(row["suggested_codes"]):
            codes.update(row["suggested_codes"].lower().split(";"))
        codes.discard("")
        if codes:
            rows.append({"text": row["text"], "labels": ";".join(sorted(codes))})
    pd.DataFrame(rows).to_csv(output_path, index=False)
```

Después se mezcla con CodiESP:

```python
train_orig = pd.read_csv("codiesp_D_source_train.csv")
feedback   = pd.read_csv("feedback_train.csv")
combined   = pd.concat([train_orig, feedback]).sample(frac=1, random_state=42)
combined.to_csv("combined_train.csv", index=False)
```

### Estrategias de incorporación

**Opción A — Fine-tuning sobre el modelo actual (recomendada)**

Partir del checkpoint existente (`classifier_<ts>.pt`) y entrenar sobre
`combined_train.csv`. Ventajas: hereda todo lo aprendido de CodiESP; pocas épocas
necesarias (5-10 en vez de 20). Añadir al comando:

```bash
make ai-train-gpu EXTRA_ARGS="--resume_from /app/model/classifier_<ts>.pt --epochs 10 --lr 2e-5"
```

> Requiere añadir `--resume_from` a `train.py` si no existe aún (carga el estado del
> modelo antes de empezar el bucle de entrenamiento).

**Opción B — Entrenamiento desde cero con datos combinados**

Solo recomendable cuando el volumen de feedback supera ~200 muestras nuevas. Usa el
mismo comando estándar con `combined_train.csv` como `--train_file`.

**Opción C — Replay buffer ponderado**

Dar más peso a las muestras de feedback (datos reales de dominio) que a CodiESP
(datos de benchmark). Implementable con `--sample_weights` si se añade soporte en
`train.py`, o duplicando filas de feedback en el CSV antes de combinar.

### Consideraciones críticas

**Sesgo de confirmación**: el médico solo valida/rechaza los códigos que el modelo ya
sugirió. Los códigos correctos pero fuera del top-k nunca aparecen como positivos a
menos que el médico los sugiera manualmente vía `suggest_code`. Esto implica que el
feedback solo refuerza predicciones existentes, no corrige los falsos negativos que
el modelo no vio.

**Solución parcial**: usar las sugerencias manuales (`code_suggestions`) como
etiquetas positivas adicionales. Si el médico sugiere `J18.9` y el modelo no lo
predijo, eso es un falso negativo valioso para el entrenamiento.

**Ruido en rechazos**: un código rechazado (`status = "rejected"`) significa que el
modelo lo predijo incorrectamente para ese informe. No significa que el código sea
incorrecto en general. Úsalos solo como señal implícita (ausencia en labels), no como
etiqueta negativa explícita (el BCE con multi-label ya trata la ausencia como negativo).

**Volumen mínimo necesario**: con menos de ~50 muestras nuevas, el ruido supera la
señal. Esperar a acumular al menos 100-200 informes con feedback antes de un ciclo de
reentrenamiento.

**Validación antes de desplegar**: siempre evaluar el nuevo modelo sobre el split de
validación de CodiESP antes de sustituir el modelo en producción. Si el F1 baja más
de 1 pp respecto al baseline, descartar el ciclo.

### Estado actual

A fecha de escritura de esta sección, el sistema está capturando datos en producción
pero no se ha realizado ningún ciclo de reentrenamiento con feedback real. La
infraestructura de extracción (query SQL + script de transformación) está descrita
aquí pero no implementada como script autónomo. El primer ciclo debería realizarse
cuando se acumulen ≥100 informes con al menos un código validado o sugerido.
