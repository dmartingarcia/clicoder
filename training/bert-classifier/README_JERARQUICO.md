# Clasificador Jerárquico CIE-10 de 2 Niveles

## 🎯 Visión General

Este sistema implementa una estrategia **profesional de Extreme Multi-label Classification (XMC)** para predecir códigos CIE-10 a partir de informes médicos en español.

### ¿Por qué jerárquico?

Con **~14,000 códigos CIE-10**, un clasificador plano sería:
- ❌ Computacionalmente costoso (matriz de salida enorme)
- ❌ Lento en inferencia
- ❌ Difícil de entrenar con datos limitados
- ❌ Propenso a overfitting

El enfoque jerárquico reduce el espacio de búsqueda **95%** (14K → ~700 códigos por capítulo).

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    Texto del Informe                    │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │  NIVEL 1: Clasificador de   │
         │  Capítulos CIE-10           │
         │  (19 clases)                │
         └─────────────┬───────────────┘
                       │
                       │ Top-3 Capítulos
                       │ (ej: IX, X, XIII)
                       ▼
         ┌─────────────────────────────┐
         │  NIVEL 2: Clasificador de   │
         │  Códigos Específicos        │
         │  (~700 códigos por capítulo)│
         └─────────────┬───────────────┘
                       │
                       │ Top-5 códigos/cap
                       ▼
         ┌─────────────────────────────┐
         │  Agregación y Ranking       │
         │  Top-10 códigos finales     │
         └─────────────────────────────┘
```

### Ventajas

1. **Reducción de espacio de búsqueda**: 14,000 → ~700 códigos
2. **Más rápido**: 2 pasadas pequeñas vs 1 pasada gigante
3. **Mejor precisión**: Modelos especializados por dominio
4. **Explicabilidad**: "Este informe trata de Cap. IX (Circulatorio) → código I10"
5. **Escalable**: Fácil añadir nuevos códigos o capítulos

## 📚 Componentes

### 1. Mapeo de Capítulos CIE-10

21 capítulos oficiales de la CIE-10:
- **I**: A00-B99 - Enfermedades infecciosas
- **II**: C00-D48 - Neoplasias
- **IX**: I00-I99 - Sistema circulatorio
- **X**: J00-J99 - Sistema respiratorio
- ...

### 2. Nivel 1: ChapterClassifier

- **Entrada**: Texto del informe médico (máx 512 tokens)
- **Salida**: Probabilidades para 19-21 capítulos
- **Modelo**: RoBERTa-Clinical (PlanTL-GOB-ES/roberta-base-biomedical-clinical-es)
- **Entrenamiento**: 15 epochs, batch 16 (GPU) / 8 (CPU)

### 3. Nivel 2: CodeClassifier

- **Entrada**: Texto del informe médico
- **Salida**: Probabilidades para todos los códigos CIE-10
- **Modelo**: RoBERTa-BSC (mismo que Nivel 1)
- **Entrenamiento**: 10 epochs, batch 8 (GPU) / 4 (CPU)
- **Filtrado**: Solo considera códigos de capítulos predichos en Nivel 1

### 4. Pipeline de Cascada

```python
texto → Nivel1(top-3 caps) → Nivel2(códigos en esos caps) → Top-10
```

## 🚀 Uso

### Entrenamiento

```bash
# Activar entorno
cd training/bert-classifier
source venv/bin/activate

# Abrir notebook
jupyter notebook clasificador_jerarquico_2niveles.ipynb

# Ejecutar todas las celdas
# Tiempo estimado: 3-4 horas en CPU, 1 hora en GPU
```

### Inferencia

```python
from transformers import AutoTokenizer
import torch

# Cargar modelos exportados
chapter_model = ChapterClassifier(...)
code_model = CodeClassifier(...)

# Crear clasificador jerárquico
classifier = HierarchicalCIE10Classifier(
    chapter_model=chapter_model,
    code_model=code_model,
    tokenizer=tokenizer,
    ...
)

# Predecir
texto = "Paciente con hipertensión arterial..."
predicciones = classifier.predict(texto, top_k=10)

# Resultado: [(código, probabilidad, capítulo), ...]
# Ej: [('I10', 0.92, 'IX'), ('I11', 0.76, 'IX'), ...]
```

## 📊 Hiperparámetros

### Configuración Adaptativa

| Parámetro | CPU | GPU |
|-----------|-----|-----|
| Batch Size Nivel 1 | 8 | 16 |
| Batch Size Nivel 2 | 4 | 8 |
| Epochs Nivel 1 | 15 | 15 |
| Epochs Nivel 2 | 10 | 10 |

### Cascading

- `TOP_K_CHAPTERS`: 3 (capítulos a considerar)
- `TOP_K_CODES_PER_CHAPTER`: 5 (códigos por capítulo)
- `FINAL_TOP_K`: 10 (códigos finales)
- `THRESHOLD_LEVEL1`: 0.3 (confianza mínima capítulo)
- `THRESHOLD_LEVEL2`: 0.5 (confianza mínima código)

## 🎯 Modelo: RoBERTa-BSC

### ¿Por qué RoBERTa-BSC?

✅ **Especializado en español médico** (BSC = Barcelona Supercomputing Center)
✅ **Mejor F1 en CODIESP**: 0.82 vs 0.75 (BERT Spanish)
✅ **125M parámetros**: Balance velocidad/precisión
✅ **Pre-entrenado en corpus médico**: PubMed, SciELO, textos clínicos

### Alternativas Evaluadas

Ver [ANALISIS_MODELOS.md](./ANALISIS_MODELOS.md) para comparativa completa:
- RoBERTa-large-BSC (355M params) - Más preciso pero 3x más lento
- BERT Spanish WWM (110M params) - F1 0.75, genérico
- DistilBERT Multi (134M params) - Rápido pero F1 0.68
- MiniLM Multi (22M params) - Muy rápido pero F1 0.60

## 📁 Archivos Generados

```
training/bert-classifier/
├── clasificador_jerarquico_2niveles.ipynb  # Notebook principal
├── ANALISIS_MODELOS.md                      # Comparativa de modelos
├── snapshots/
│   ├── nivel1_capitulos/
│   │   └── best_model.pt                    # Nivel 1 entrenado
│   └── nivel2_codigos/
│       └── best_model.pt                    # Nivel 2 entrenado
└── ../../ai_engine/model/
    ├── chapter_classifier.pt                # Exportado para producción
    ├── code_classifier.pt                   # Exportado para producción
    ├── config.json                          # Configuración
    └── cie10_chapters.json                  # Mapeo de capítulos
```

## 🔬 Dataset: CODIESP

- **Corpus**: ~1000 documentos clínicos en español
- **Anotaciones**: Códigos CIE-10 por expertos médicos
- **Train**: 750 docs
- **Dev**: 250 docs
- **Tamaño**: 1.2 GB

## 📈 Métricas Esperadas

### Nivel 1 (Capítulos)
- **F1 Micro**: ~0.85-0.90
- **F1 Macro**: ~0.75-0.80
- **Precision**: ~0.87
- **Recall**: ~0.83

### Nivel 2 (Códigos)
- **F1 Micro**: ~0.70-0.75
- **F1 Macro**: ~0.55-0.60
- **Precision**: ~0.73
- **Recall**: ~0.68

### Sistema Completo (Cascada)
- **F1 Micro**: ~0.68-0.72
- **Top-10 Accuracy**: ~0.80-0.85

## 🚀 Próximos Pasos

1. **RAG para Explicabilidad**: Añadir retrieval de definiciones CIE-10
2. **Fine-tuning por Especialidades**: Modelos específicos para cardiología, oncología, etc.
3. **Active Learning**: Seleccionar casos difíciles para re-anotación
4. **Ensemble**: Combinar predicciones de múltiples modelos

## 📝 Notas

- El modelo base funciona bien en **CPU** (8-10 predicciones/seg)
- **GPU recomendada** para entrenamiento (4x más rápido)
- Los modelos exportados son compatibles con **FastAPI** (ai_engine)

## 🔗 Referencias

- **Modelo**: [PlanTL-GOB-ES/roberta-base-biomedical-clinical-es](https://huggingface.co/PlanTL-GOB-ES/roberta-base-biomedical-clinical-es)
- **Dataset**: [CODIESP](https://temu.bsc.es/codiesp/)
- **Paper**: Miranda-Escalada et al., "Overview of CODIESP" (2020)


## Capitulos

Celdas 1-11: Imports, config, mapeo capítulos, carga de datos
Celda 13: ChapterDataset (dataset para capítulos)
Celda 14: ChapterClassifier (modelo Nivel 1)
Celda 15: Funciones de entrenamiento (train_epoch, evaluate)
Celda 16: Setup Nivel 1 (crea tokenizer, datasets, model, optimizer, scheduler)
Celda 17: ⏱️ Entrenamiento Nivel 1 (15 épocas, ~1.5h CPU)
Celda 18: CodeClassifier (modelo Nivel 2)
Celda 19: Setup Nivel 2 (crea datasets de códigos, model, optimizer, scheduler)
Celda 20: CodeDataset (dataset para códigos específicos)
Celda 21: ⏱️ Entrenamiento Nivel 2 (10 épocas, ~2h CPU)
Celda 22: Ejemplo de predicción
Celda 23: Exportar modelos a producción
Celda 24: Cargar modelos entrenados
Celda 26: HierarchicalCIE10Classifier (pipeline jerárquico completo)