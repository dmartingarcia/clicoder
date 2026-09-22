# Motor de IA — inventario de guiones

Qué hace cada fichero de `ai_engine/` y cuándo se usa. El servicio en producción solo necesita
los del primer bloque; el resto son herramientas de entrenamiento, evaluación y análisis.

## Servicio

| Fichero | Qué hace |
|---|---|
| `main.py` | Servicio FastAPI. Expone `/predict` (cuatro motores: `bert`, `dict`, `both`, `fused`), `/explain`, `/summarize/stream` y el panel de administración del *summarizer*. |
| `classifier.py` | Carga el modelo entrenado y expone `predict()` y `explain()`. Contiene el registro de estrategias de atribución. |
| `baseline_dict.py` | Clasificador de diccionario por coincidencia léxica. Predice bloques de 3 caracteres; se usa solo, fusionado con el modelo, y como fuente de explicaciones instantáneas. |
| `summarizer.py` | Resumen o paráfrasis del informe con un LLM local en formato GGUF. |

## Entrenamiento

| Fichero | Qué hace |
|---|---|
| `train.py` | Entrena el clasificador. Admite pre-entrenamiento sobre el catálogo CIE-10, descongelado progresivo, destilación desde otros *checkpoints* y las pérdidas experimentales (ZLPR, R-Drop, media móvil de pesos). |
| `augment.py` | Aumentación por retrotraducción, con NLLB-200 local o Azure Translator. |
| `augment_paraphrase.py` | Aumentación por paráfrasis con un LLM. |
| `combine_augmented.py` | Une el corpus original con las variantes generadas por los guiones anteriores. |

## Evaluación

| Fichero | Qué hace |
|---|---|
| `eval_test.py` | Evalúa el modelo de producción sobre el conjunto de prueba. Es la fuente de las cifras titulares del trabajo: precisión completa, barrido de umbral sobre validación. |
| `ensemble_eval.py` | Evalúa varios *checkpoints* y su promedio en una sola pasada. Al compartir pasada, sus cifras son comparables entre sí aunque difieran en la tercera decimal de las de `eval_test.py`. |
| `compare_runs.py` | Contrasta dos grupos de ejecuciones con la prueba *t* de Welch. Existe porque con este corpus el ruido entre semillas es del orden del efecto que se quiere medir, y comparar ejecuciones sueltas produce conclusiones que no se reproducen. |
| `merge_runs.py` | Consolida en el CSV canónico los `training_runs.csv` de ejecuciones lanzadas en paralelo. |
| `rerank_map.py` | Reordenación posterior de las salidas: calibración entre clases y fusión con el diccionario. Cachea los *logits* para repetir barridos sin volver a pasar el *encoder*. |
| `soup.py` | Promedia los pesos de varios *checkpoints* en un único modelo, buscando la ganancia del promediado sin su coste de inferencia. |
| `baseline_tfidf.py` | Línea base clásica (TF-IDF y regresión logística) para contextualizar los resultados. |

## Bancos de prueba de explicabilidad

| Fichero | Qué hace |
|---|---|
| `bench_explain.py` | Curva de coste y fidelidad de las estrategias de atribución frente a la exhaustiva. |
| `bench_dicc.py` | Latencia, cobertura y solape del método de diccionario frente al exhaustivo. |
| `bench_dispersion.py` | Mide cuán dispersa es la importancia por palabra, que es lo que decide si la poda por grupos puede compensar. |

## Figuras

| Fichero | Qué hace |
|---|---|
| `plot_runs.py` | Comparativa de todas las ejecuciones de entrenamiento. |
| `plot_tfg_figures.py` | Figuras de datos del TFG a partir de resultados reales. |

## Artefactos en `model/`

Los `.pt` y la caché de *logits* no están versionados (ver `.gitignore`): son grandes y
reproducibles. Sí se versionan los resultados de evaluación (`eval_*.json`,
`fusion_sweep.json`, `comparativa_motores.json`) y el registro de ejecuciones
(`training_runs.csv`), porque son las cifras que cita la memoria.
