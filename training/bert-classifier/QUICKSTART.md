# Inicio Rápido - Clasificador Jerárquico CIE-10

## Entrenamiento en 3 Pasos

### 1. Preparar Entorno

```bash
cd /Users/david/own/CIE10-project/training/bert-classifier

# Activar entorno virtual
source venv/bin/activate

# Verificar dependencias (ya deberían estar instaladas)
pip list | grep -E "torch|transformers|scikit-learn"
```

### 2. Abrir Notebook

```bash
# Iniciar Jupyter
jupyter notebook

# O si prefieres VS Code
code clasificador_jerarquico_2niveles.ipynb
```

### 3. Ejecutar Todo

En el notebook:
- **Opción A**: Click en "Run All"
- **Opción B**: Cell → Run All
- **Opción C**: Ejecutar celda por celda (recomendado para ver progreso)

## Tiempos de Entrenamiento

| Hardware | Nivel 1 | Nivel 2 | Total |
|----------|---------|---------|-------|
| **CPU** (M1 Mac) | ~1.5h | ~2h | ~3.5h |
| **GPU** (CUDA) | ~20 min | ~40 min | ~1h |

## Qué Esperar

### Durante el Entrenamiento

```
Iniciando entrenamiento Nivel 1: Clasificador de Capítulos

Datasets creados: 750 train, 250 dev
Número de capítulos: 21

Epoch 1/15
   Training: 100%|████████████| 94/94 [00:45<00:00]
   Train Loss: 0.1234
   Dev F1 Micro: 0.8567
   Mejor modelo guardado! F1=0.8567

Epoch 2/15
   ...
```

### Al Finalizar

```
Entrenamiento Nivel 1 completado!
Mejor F1 Micro: 0.8842

Entrenamiento Nivel 2 completado!
Mejor F1 Micro: 0.7123

Exportando modelos para producción...
Nivel 1 exportado: ../../ai_engine/model/chapter_classifier.pt
Nivel 2 exportado: ../../ai_engine/model/code_classifier.pt
Configuración exportada: ../../ai_engine/model/config.json

Exportación completada!
```

## Probar el Modelo

### Desde el Notebook (última celda)

```python
# Ya está listo, solo ejecutar la celda #10
# Verás predicciones sobre un ejemplo del dataset

# Salida esperada:
Predicciones del modelo jerárquico:
============================================================
1. I10 (Cap. IX)
   Probabilidad: 0.9234
   Capítulo: Enfermedades del sistema circulatorio

2. I11 (Cap. IX)
   Probabilidad: 0.7654
   Capítulo: Enfermedades del sistema circulatorio
...
```

### Desde Python

```python
# Crear nuevo script test_classifier.py
from transformers import AutoTokenizer
import torch

# Cargar modelos exportados
checkpoint_level1 = torch.load('../../ai_engine/model/chapter_classifier.pt')
checkpoint_level2 = torch.load('../../ai_engine/model/code_classifier.pt')

# ... (ver README_JERARQUICO.md para código completo)

# Probar con tu propio texto
texto = """
Paciente de 65 años con hipertensión arterial esencial,
diabetes mellitus tipo 2 descompensada y cardiopatía isquémica.
Refiere dolor precordial de inicio súbito hace 2 horas.
"""

predicciones = classifier.predict(texto, top_k=10)
for code, prob, chapter in predicciones:
    print(f"{code} ({prob:.3f}) - Cap. {chapter}")
```

## Siguiente Paso: Integrar en ai_engine

Una vez entrenado, los modelos están listos para usar en producción:

```bash
cd ../../ai_engine

# Verificar que los modelos están exportados
ls -lh model/
# Deberías ver: chapter_classifier.pt, code_classifier.pt, config.json

# Actualizar main.py para usar el clasificador jerárquico
# (ver documentación en README_JERARQUICO.md)
```

## Troubleshooting

### Error: CUDA out of memory

```python
# En la celda de configuración, ajusta:
BATCH_SIZE_LEVEL1 = 4  # En vez de 8
BATCH_SIZE_LEVEL2 = 2  # En vez de 4
```

### Error: Slow performance on CPU

```python
# Reduce max_length:
MAX_LENGTH = 256  # En vez de 512
```

### Error: Can't find CODIESP data

```bash
# Verifica que descargaste los datos:
ls -lh ../codiesp/
# Deberías ver: train.tsv, dev.tsv

# Si no están, descarga desde:
# https://zenodo.org/record/3837305
```

## Monitorear Progreso

### Tensorboard (opcional)

```bash
# Si quieres visualizar métricas en tiempo real:
pip install tensorboard
tensorboard --logdir=snapshots/
```

### Logs

```bash
# Ver logs de entrenamiento:
tail -f snapshots/nivel1_capitulos/training.log
```

## Checklist Pre-Entrenamiento

- [ ] Entorno virtual activado
- [ ] Dataset CODIESP descargado (1.2GB)
- [ ] Dependencias instaladas (torch, transformers, scikit-learn)
- [ ] Espacio en disco: ~5GB libre
- [ ] Tiempo disponible: 1-4 horas según hardware
