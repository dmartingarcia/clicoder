# Análisis Estadístico de Datos CIE-10 y CODIESP

Este directorio contiene análisis estadísticos detallados de los conjuntos de datos relacionados con CIE-10-ES (diagnósticos, procedimientos y productos químicos) y los datos de CODIESP, un conjunto de textos clínicos en español con etiquetas de diagnóstico.

## Contenido

### Notebooks de Análisis

- `cie10_analisis_estadistico.ipynb`: Análisis estadístico completo de los conjuntos de datos CIE-10-ES.
- `codiesp_analisis_estadistico.ipynb`: Análisis estadístico detallado de los conjuntos de datos CODIESP.
- `cie10_spacy_word_analysis.ipynb`: Análisis lingüístico avanzado con SpaCy de las descripciones CIE-10 y validación cruzada con CODIESP.
- `analisis_linguistico_jerarquico.ipynb`: Análisis jerárquico de términos lingüísticos en los datos.

### Documentación

- `DOCUMENTATION.md`: Documentación general del análisis estadístico.
- `DOCUMENTATION_SPACY_ANALYSIS.md`: Documentación completa del análisis lingüístico de CIE-10 con SpaCy, incluyendo la validación cruzada con CODIESP.
- `DOCUMENTATION_CODIESP.md`: Documentación específica del análisis de los datos CODIESP.
- `DOCUMENTATION_LINGUISTICO_JERARQUICO.md`: Documentación del análisis lingüístico jerárquico.
- `validation_results.json`: Resultados de la comparación entre CIE-10 y CODIESP en formato JSON.

## Conjuntos de Datos Analizados

### CIE-10-ES

1. **Diagnósticos (cie10-es-diagnoses.csv)**: Códigos CIE-10 para diagnósticos médicos.
2. **Procedimientos (cie10-es-procedures.csv)**: Códigos de procedimientos médicos basados en CIE-10.
3. **Químicos (cie10-es-chemicals.csv)**: Información sobre productos químicos y sustancias relacionadas.

### CODIESP

1. **Train**: Conjunto de entrenamiento con textos clínicos y sus etiquetas.
2. **Test**: Conjunto de prueba para evaluar modelos.
3. **Validation**: Conjunto de validación para ajuste de modelos.

## Análisis Realizados

- Exploración inicial de estructura de datos
- Estadísticas descriptivas
- Distribución de categorías de diagnósticos, procedimientos y químicos
- Análisis de textos clínicos (longitud, palabras frecuentes)
- Análisis de etiquetas de diagnóstico
- Relaciones entre textos y etiquetas
- Comparaciones entre conjuntos
- Análisis lingüístico con SpaCy (lematización, POS tagging)
- Validación cruzada entre vocabularios CIE-10 y CODIESP
- Análisis de n-gramas y patrones sintácticos
- Integración con embeddings contextuales

## Resultados Clave

Los hallazgos detallados se encuentran en los archivos de documentación. Algunos resultados clave incluyen:

- Distribución desigual de códigos CIE-10 en todos los conjuntos
- Correlación positiva entre la longitud de textos clínicos y el número de etiquetas
- Características consistentes entre los conjuntos de entrenamiento, validación y prueba de CODIESP
- Identificación de categorías principales de diagnósticos, procedimientos y productos químicos

## Software Utilizado

- Python 3.x
- Pandas, NumPy
- Matplotlib, Seaborn, Plotly
- SpaCy con modelo es_core_news_lg para análisis lingüístico avanzado
- NLTK para procesamiento de texto
- Pickle para sistema de caché

## Archivos de Datos Generados

- `cie10_word_analysis.csv`: Análisis de palabras del vocabulario CIE-10.
- `codiesp_word_analysis.csv`: Análisis de palabras del corpus CODIESP.
- `common_medical_vocabulary.csv`: Vocabulario médico común entre CIE-10 y CODIESP.
- `cache/`: Directorio con archivos de caché para optimizar el procesamiento.
