# 🎯 Entrenamiento del Modelo CIE-10

Sistema automatizado para entrenar un clasificador jerárquico de códigos CIE-10 usando BERT y el corpus CODIESP.

## 🚀 Quick Start

### Opción 1: Pipeline Automático Completo (Recomendado)

Desde la raíz del proyecto:

```bash
make train-all
```

Esto ejecutará automáticamente:
1. ✅ Configuración del entorno Python
2. ✅ Descarga del dataset CODIESP
3. ✅ Entrenamiento del modelo
4. ✅ Exportación a `ai_engine/`
5. ✅ Rebuild y restart del contenedor

**⚠️ Nota:** El entrenamiento puede tardar **varias horas** dependiendo de tu hardware.

### Opción 2: Paso a Paso

```bash
# 1. Configurar entorno
make train-setup

# 2. Entrenar modelo (abre Jupyter para control manual)
make train-jupyter
# Ejecuta todas las celdas del notebook 'clasificador_jerarquico.ipynb'

# 3. Exportar modelo entrenado
make train-export
```

## 📋 Comandos Disponibles

Desde la **raíz del proyecto**:

| Comando | Descripción |
|---------|-------------|
| `make train-all` | Pipeline completo automatizado |
| `make train-setup` | Configurar entorno de entrenamiento |
| `make train-dataset` | Descargar dataset CODIESP |
| `make train-jupyter` | Abrir Jupyter Notebook |
| `make train-model` | Entrenar modelo (ejecución automática) |
| `make train-export` | Exportar modelo a ai_engine |
| `make train-clean` | Limpiar entornos virtuales |

Desde **training/**:

```bash
cd training

make setup      # Configurar entorno
make dataset    # Descargar dataset
make jupyter    # Abrir Jupyter
make train      # Entrenar automáticamente
make export     # Exportar modelo
make all        # Todo lo anterior
```

Desde **training/bert-classifier/**:

```bash
cd training/bert-classifier

make venv       # Crear entorno virtual
make install    # Instalar dependencias
make jupyter    # Abrir notebook
make train      # Entrenar modelo
make export-model  # Exportar a ai_engine
```

## 🏗️ Arquitectura

```
training/
├── Makefile                    # Orquestador principal
├── csv_import_scripts/         # Descarga de datasets
│   ├── Makefile
│   ├── collect_codiesp_dataset.py
│   └── codiesp_csvs/           # Dataset descargado (1.2GB)
│       ├── codiesp_D_source_train.csv
│       ├── codiesp_D_source_test.csv
│       └── codiesp_D_source_validation.csv
│
└── bert-classifier/            # Entrenamiento del modelo
    ├── Makefile
    ├── requirements.txt
    ├── clasificador_jerarquico.ipynb  # 🎓 Notebook principal
    └── snapshots/                     # Modelo entrenado
        ├── best_hierarchical_model/
        ├── best_hierarchical_model_state.bin
        ├── best_hierarchical_model_mlb/
        └── cie10_tokenizer/
```

## 🎓 Modelo

**Arquitectura:** BERT jerárquico multietiqueta

**Características:**
- **Modelo base:** `dccuchile/bert-base-spanish-wwm-cased`
- **Clasificación jerárquica:** Padre → Hijo → Nieto (ej: I → I10 → I10.1)
- **Dataset:** CODIESP (corpus médico español)
- **Métricas:** F1-score macro/micro por nivel

**Hiperparámetros por defecto:**
```python
MAX_LENGTH = 512
BATCH_SIZE = 8
EPOCHS = 500
LEARNING_RATE = 5e-5
```

## 📊 Dataset CODIESP

**Fuente:** BigBio/HuggingFace (`bigbio/codiesp`)

**Contenido:**
- **Train:** ~1000 documentos clínicos
- **Validation:** ~500 documentos
- **Test:** ~500 documentos

**Tamaño total:** ~1.2GB

El dataset se descarga automáticamente con `make train-dataset` o `make train-setup`.

## 🔧 Requisitos

### Hardware Recomendado
- **CPU:** 8+ cores
- **RAM:** 16GB+
- **GPU:** CUDA compatible (opcional, acelera 10-20x)
- **Disco:** 5GB libres

### Software
- Python 3.8+
- pip
- virtualenv
- make

## 📝 Notas Importantes

### Tiempo de Entrenamiento

| Hardware | Tiempo Estimado |
|----------|-----------------|
| CPU (8 cores) | 12-24 horas |
| GPU (RTX 3080) | 2-4 horas |
| GPU (RTX 4090) | 1-2 horas |

### Consumo de Recursos

Durante el entrenamiento:
- **RAM:** 8-12GB
- **VRAM (GPU):** 6-8GB
- **CPU:** 80-100% (si no hay GPU)

### Callbacks y Checkpoints

El modelo guarda automáticamente:
- ✅ Checkpoint del mejor modelo (por F1-score)
- ✅ Tokenizer configurado
- ✅ MultiLabelBinarizer (mlb) para etiquetas
- ✅ Estado completo del modelo

## 🐛 Troubleshooting

### Error: Out of Memory
```bash
# Reducir batch size en el notebook:
TRAIN_BATCH_SIZE = 4  # En lugar de 8
```

### Error: Dataset not found
```bash
cd training
make dataset
```

### Error: CUDA not available
El modelo funciona en CPU, pero será más lento. No requiere GPU.

### Error: Jupyter kernel died
Reduce el batch size o cierra otras aplicaciones que consuman RAM.

## 🔄 Actualizar Modelo en Producción

Después de entrenar:

```bash
# Exportar modelo
make train-export

# Rebuild ai_engine con nuevo modelo
docker compose build ai_engine
docker compose up -d ai_engine

# Verificar
docker compose logs ai_engine
```

## 📚 Referencias

- [CODIESP Dataset](https://huggingface.co/datasets/bigbio/codiesp)
- [BERT Spanish](https://huggingface.co/dccuchile/bert-base-spanish-wwm-cased)
- [Transformers Library](https://huggingface.co/docs/transformers)

## 💡 Tips

1. **Primera vez:** Usa `make train-jupyter` para ver el proceso paso a paso
2. **Producción:** Usa `make train-all` para automatizar todo
3. **Debug:** Reduce epochs a 10-20 para pruebas rápidas
4. **Mejores resultados:** Entrena con GPU por 500 epochs

---

**¿Listo para empezar?**

```bash
make train-all
```

☕ Ve por un café mientras el modelo entrena...
