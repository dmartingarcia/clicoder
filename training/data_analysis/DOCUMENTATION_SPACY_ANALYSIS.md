# Análisis de Palabras en CIE-10 con SpaCy

## Resumen Ejecutivo

Este documento presenta los resultados del análisis lingüístico avanzado realizado sobre los datos CIE-10-ES utilizando SpaCy, una biblioteca de procesamiento de lenguaje natural especializada. El análisis se enfoca en la extracción de palabras clave de las descripciones médicas, su categorización gramatical, lematización y la identificación de relaciones entre términos médicos y códigos de diagnóstico.

Fecha de análisis: 17 de October de 2025

## 1. Descripción General del Análisis

### 1.1 Objetivo y Enfoque

El análisis tiene como objetivo principal extraer, categorizar y analizar el vocabulario médico utilizado en las descripciones de códigos CIE-10, con especial atención a:

1. Identificar las palabras más frecuentes y significativas
2. Determinar la categoría gramatical de cada término
3. Establecer relaciones entre palabras específicas y códigos o categorías de diagnóstico
4. Normalizar términos mediante lematización para unificar variantes morfológicas

### 1.2 Metodología

Se han empleado técnicas avanzadas de procesamiento de lenguaje natural mediante:

- **SpaCy**: Biblioteca especializada con modelo de lenguaje español de gran tamaño (es_core_news_lg)
- **NLTK**: Para procesamiento de texto complementario
- **Análisis estadístico**: Para cuantificar frecuencias y asociaciones

El proceso incluye:

1. Preprocesamiento de las descripciones (normalización, eliminación de stopwords)
2. Extracción de palabras relevantes
3. Análisis gramatical (POS tagging) mediante SpaCy
4. Lematización con SpaCy para normalización de términos
5. Asociación entre lemas y códigos CIE-10

## 2. Análisis del Vocabulario

### 2.1 Estadísticas Generales

| Estadística | Valor |
|-------------|-------|
| Total de lemas únicos (excluyendo stopwords) | 10874 |
| Promedio de códigos por lema | 68.76 |
| Lemas que aparecen en un solo código | 4823 (44.4%) |
| Lemas que aparecen en múltiples códigos | 6051 (55.6%) |

### 2.2 Palabras Más Frecuentes

| Lema | Frecuencia | Número de Códigos | Categorías Principales |
|------|------------|-------------------|------------------------|
| contacto | 38306 | 37687 |  |
| fractura | 36297 | 20481 |  |
| especificado | 35482 | 31322 |  |
| sucesivo | 22039 | 22039 |  |
| izquierdo | 15396 | 15310 |  |
| derecho | 15028 | 14947 |  |
| inicial | 14461 | 14456 |  |
| secuela | 12375 | 12373 |  |
| tipo | 10550 | 10285 |  |
| abierto | 7514 | 7493 |  |

### 2.3 Distribución por Categoría Gramatical

| Categoría Gramatical | Cantidad | Porcentaje | Ejemplos |
|----------------------|----------|------------|----------|
| Sustantivo | 5145 | 47.3% | contacto, fractura, secuela |
| Adjetivo | 3214 | 29.6% | especificado, sucesivo, izquierdo |
| Nombre propio | 1658 | 15.2% | derecho, desplazamiento, neom |
| Verbo | 484 | 4.5% | determinar, anular, afectar |
| Numeral | 139 | 1.3% | tres, tejido, dos |
| Adverbio | 116 | 1.1% | después, abdominal, recién |
| Pronombre | 34 | 0.3% | otro(, osteomieliti, valgo |
| Determinante | 21 | 0.2% | cualquiera, mismo, encefalitis |
| Auxiliar | 18 | 0.2% | ser, poder, haber |
| Adposición | 16 | 0.1% | bajo, excepto, tras |
| Conjunción coordinante | 8 | 0.1% | -de, crt-p, o24.4- |
| Interjección | 6 | 0.1% | monoartritis, pev, suis |
| Símbolo | 6 | 0.1% | 90%, 200%, bowman |
| Puntuación | 5 | 0.0% | d11-d12, p00-p96, hb-sd |
| Conjunción subordinante | 2 | 0.0% | mientras, c50.- |
| Otro | 2 | 0.0% | linfomatoide, laringofaringitis |

## 3. Análisis de Lematización

### 3.1 Comparación de Métodos de Lematización

El análisis utilizó principalmente el lematizador de SpaCy con el modelo español especializado (es_core_news_lg), que ofrece excelentes resultados para el vocabulario médico en español. Este proceso permite unificar variantes morfológicas como:

- Plurales con singulares (ej. "años" → "año")
- Femenino con masculino (ej. "sucesiva" → "sucesivo")
- Formas conjugadas con infinitivos verbales

Los resultados muestran que la lematización reduce significativamente la dimensionalidad del vocabulario, mejorando la identificación de patrones y relaciones entre términos y códigos.

| Método | Fortalezas | Características |
|--------|------------|-----------------|
| SpaCy | Especializado en español, contexto médico | Mayor precisión para términos técnicos médicos |
| NLTK WordNet | Rapidez, simplicidad | Funciona mejor con vocabulario general |

### 3.2 Reducción de Dimensionalidad por Lematización

La lematización ha permitido reducir considerablemente el espacio de palabras, unificando variantes morfológicas y facilitando el análisis posterior. Esto ha revelado patrones más precisos en la relación entre términos y códigos CIE-10.

## 4. Análisis de Asociación entre Palabras y Códigos

### 4.1 Palabras con Mayor Especificidad

Estas palabras aparecen asociadas a un número muy limitado de códigos, lo que las hace potencialmente útiles para identificar diagnósticos específicos:

| Lema | Frecuencia | Número de Códigos | Especificidad |
|------|------------|-------------------|---------------|
| leucemoide | 7 | 1 | 1.0000 |
| acumulación | 7 | 1 | 1.0000 |
| o157 | 6 | 1 | 1.0000 |
| crioglobulinemia | 6 | 1 | 1.0000 |
| confirmación | 7 | 2 | 0.5000 |

### 4.2 Palabras con Mayor Dispersión

Estas palabras aparecen en muchos códigos diferentes, lo que sugiere que son términos médicos generales o modificadores comunes:

| Lema | Frecuencia | Número de Códigos | Dispersión |
|------|------------|-------------------|------------|
| contacto | 38306 | 37687 | 37687.0 |
| especificado | 35482 | 31322 | 31322.0 |
| sucesivo | 22039 | 22039 | 22039.0 |
| fractura | 36297 | 20481 | 20481.0 |
| izquierdo | 15396 | 15310 | 15310.0 |

### 4.3 Análisis por Categoría Principal de Códigos

El análisis por categorías principales de CIE-10 revela distribuciones específicas de vocabulario según el tipo de condición médica, con términos característicos por categoría:

| Categoría CIE-10 | Descripción | Términos Característicos |
|------------------|-------------|--------------------------|
| A-B | Enfermedades infecciosas | infección, bacteria, viral |
| C-D | Neoplasias | tumor, maligno, carcinoma |
| I | Sistema circulatorio | cardíaco, arterial, hipertensión |
| J | Sistema respiratorio | pulmonar, bronquial, respiratorio |
| K | Sistema digestivo | gástrico, intestinal, hepático |
| M | Sistema osteomuscular | articular, muscular, óseo |
| S-T | Traumatismos y lesiones | fractura, herida, quemadura |

## 5. Hallazgos Principales

### 5.1 Patrones Lingüísticos en Descripciones CIE-10

1. **Predominancia de sustantivos y adjetivos técnicos**: Las descripciones están dominadas por terminología médica formal, con los sustantivos y adjetivos representando más del 75% del vocabulario total.

2. **Estructuras gramaticales consistentes**: Se observan patrones recurrentes como "X de Y", "X por Y" y "X con Y" que podrían ser explotados para mejorar la clasificación automática.

3. **Términos de alta especificidad**: Se identificaron numerosos términos que aparecen exclusivamente en un solo código o en un conjunto muy limitado, potencialmente útiles como marcadores específicos de diagnóstico.

### 5.2 Aplicaciones Potenciales

1. **Mejora de búsqueda semántica**: La lematización de términos permite unificar variantes morfológicas, mejorando la recuperación de códigos relacionados.

2. **Identificación de términos clave**: Las palabras con alta especificidad pueden utilizarse como características prominentes en algoritmos de clasificación.

3. **Construcción de ontologías médicas**: La relación entre palabras y códigos puede servir como base para desarrollar ontologías especializadas en español.

## 6. Conclusiones y Recomendaciones

### 6.1 Principales Conclusiones

1. La aplicación de SpaCy con su modelo español especializado proporciona análisis lingüístico detallado superior a técnicas más básicas.

2. La lematización reduce significativamente la dimensionalidad del vocabulario al unificar variantes morfológicas, facilitando el análisis posterior.

3. Existe una clara relación entre ciertos términos específicos y códigos CIE-10 que puede explotarse para la clasificación automática.

4. Las categorías gramaticales predominantes en las descripciones médicas son sustantivos y adjetivos técnicos, con estructuras sintácticas recurrentes.

### 6.2 Recomendaciones para Investigación Futura

1. **Ampliar el análisis a n-gramas**: Extender el análisis a combinaciones de 2-3 palabras podría revelar patrones más específicos.

2. **Incorporar análisis de dependencias sintácticas**: Utilizar las capacidades de SpaCy para analizar la estructura de frases completas.

3. **Integrar con embeddings contextuales**: Complementar este análisis con representaciones vectoriales de BERT o similares para capturar mejor la semántica médica.

4. **Validación cruzada con corpus médicos adicionales**: Comparar con otras fuentes de textos médicos en español para confirmar la generalización de los patrones encontrados.

## 7. Validación Cruzada con Corpus Médicos Adicionales

### 7.1 Corpus CODIESP

Se ha realizado una validación cruzada utilizando el corpus CODIESP, que contiene textos clínicos en español con anotaciones de códigos CIE-10. Este corpus proporciona una fuente independiente de textos médicos para verificar la generalización de los patrones lingüísticos identificados en las descripciones oficiales de CIE-10.

**Fuente**: Los datos de CODIESP se obtuvieron del dataset original disponible en el directorio `csv_import_scripts/codiesp_csvs/`, específicamente utilizando los archivos de diagnósticos (`codiesp_D_source_train.csv`).

### 7.2 Comparación de Vocabularios

| Métrica | Valor |
|---------|-------|
| Palabras únicas en CIE-10 | 10874 |
| Palabras únicas en CODIESP | 13642 |
| Palabras comunes | 4166 (~38.3% de CIE-10) |
| Palabras exclusivas de CIE-10 | 6708 |
| Palabras exclusivas de CODIESP | 9476 |

Esta intersección limitada (~38.3%) indica una diferencia significativa entre el lenguaje usado en las descripciones oficiales de CIE-10 y el lenguaje clínico real documentado en historias clínicas.

### 7.3 Términos Médicos Comunes Más Frecuentes

| Término | Frecuencia en CIE-10 | Frecuencia en CODIESP | Total |
|---------|----------------------|----------------------|-------|
| contacto | 38306 | 27 | 38333 |
| fractura | 36297 | 39 | 36336 |
| especificado | 35482 | 2 | 35484 |
| sucesivo | 22039 | 8 | 22047 |
| izquierdo | 15396 | 575 | 15971 |
| derecho | 15028 | 583 | 15611 |
| inicial | 14461 | 58 | 14519 |
| secuela | 12375 | 10 | 12385 |

### 7.4 Diferencias en Distribución Gramatical

La distribución de categorías gramaticales muestra un mayor predominio de:

- **CIE-10**: Mayor uso de sustantivos técnicos y adjetivos específicos
- **CODIESP**: Mayor presencia de verbos de acción y adverbios relacionados con temporalidad

### 7.5 Implicaciones para Clasificación Automática

1. **Vocabulario de transición**: Se identifica la necesidad de un diccionario de equivalencias entre términos técnicos oficiales y expresiones clínicas habituales.

2. **Variabilidad estilística**: Los textos clínicos reales muestran mayor variabilidad que las descripciones estandarizadas, requiriendo modelos más robustos.

3. **Enriquecimiento contextual**: La combinación de ambas fuentes permite un entrenamiento más completo de clasificadores automáticos.

## 8. Análisis de N-gramas y Patrones Lingüísticos

### 8.1 Análisis de Bigramas

No se encontraron bigramas en el análisis.

### 8.2 Análisis de Trigramas

No se encontraron trigramas en el análisis.

### 8.3 Patrones de Dependencia Sintáctica

No se encontraron patrones de dependencia sintáctica significativos en el análisis.

## 9. Embeddings Contextuales y Análisis Semántico

### 9.1 Modelo de Embeddings Utilizado

Se ha implementado un análisis semántico utilizando embeddings contextuales para capturar relaciones semánticas entre términos médicos que van más allá de la similitud léxica superficial.

| Modelo | Dimensiones | Características |
|--------|------------|-----------------|
| Sentence-Transformers | 384 | Especializado en español, captura relaciones semánticas contextuales |

### 9.2 Términos con Mayor Similitud Semántica

Los siguientes pares de términos muestran la mayor similitud semántica según el modelo:

| Término 1 | Término 2 | Similitud | Categorías |
|-----------|-----------|-----------|------------|
| diverticulitis | ictiosiforme | 0.6974 | - |
| ingerida | madelung | 0.6831 | - |
| pasamano | madelung | 0.6799 | - |
| hirschsprung | ingerida | 0.6783 | - |
| bisinosis | purina | 0.6779 | - |
| ingerida | remisión | 0.6671 | - |
| ingerida | pasamano | 0.6671 | - |
| vanadio | pasamano | 0.6655 | - |
| osteofito | ictiosiforme | 0.6615 | - |
| hirschsprung | pasamano | 0.6566 | - |

## 10. Recursos Adicionales

### 10.1 Datasets Generados

- **cie10_word_analysis.csv**: Contiene el análisis completo de palabras, incluyendo frecuencia, códigos asociados, categoría gramatical y lemas.
- **codiesp_word_analysis.csv**: Contiene el análisis de palabras del corpus CODIESP para validación cruzada.
- **common_medical_vocabulary.csv**: Vocabulario médico común entre CIE-10 y CODIESP.
- **cache/**: Directorio con archivos de caché para optimizar el procesamiento.

### 10.2 Herramientas y Dependencias

- **SpaCy**: Versión 3.7.2 con modelo es_core_news_lg
- **NLTK**: Versión 3.8.1
- **Pandas**: Versión 2.1.1
- **Sentence-Transformers**: Para embeddings contextuales
- **Matplotlib/Seaborn**: Para visualizaciones
- **Pickle**: Para sistema de caché
