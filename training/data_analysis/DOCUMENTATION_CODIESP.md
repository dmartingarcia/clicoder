# Análisis Estadístico del Conjunto de Datos CODIESP

## Resumen Ejecutivo

Este documento presenta un análisis estadístico detallado del conjunto de datos CODIESP, que contiene textos clínicos en español con sus correspondientes códigos CIE-10-ES. El objetivo es comprender la distribución y características de estos datos para su uso en un artículo científico.

Fecha de análisis: 15 de October de 2025

## 1. Descripción General de los Datos CODIESP

### 1.1 Conjuntos de Datos Analizados

| Conjunto | Registros | Columnas | Proporción |
|----------|-----------|----------|------------|
| train | 500 | 6 | 50.00% |
| test | 250 | 6 | 25.00% |
| validation | 250 | 6 | 25.00% |
| **Total** | 1,000 | N/A | 100% |

### 1.2 Estructura de los Datos

CODIESP consiste en tres conjuntos principales:

- **Train**: Conjunto de entrenamiento para modelos de aprendizaje automático.
- **Validation**: Conjunto de validación para ajustar hiperparámetros y evaluar durante el entrenamiento.
- **Test**: Conjunto de prueba para evaluar el rendimiento final de los modelos.

Cada registro en CODIESP contiene dos campos principales:

- **text**: El texto clínico en español.
- **labels**: Una lista de códigos CIE-10-ES asociados al texto.

## 2. Estadísticas Descriptivas

### 2.1 Textos Clínicos

#### Conjunto train

| Estadística | Longitud (caracteres) | Número de palabras |
|-------------|----------------------:|-------------------:|
| Media       | 2317.25   | 349.02 |
| Desv. Est.  | 1097.44    | 164.75 |
| Mínimo      | 556    | 73 |
| Q1 (25%)    | 1517    | 225 |
| Mediana     | 2100    | 314 |
| Q3 (75%)    | 2885    | 435 |
| Máximo      | 7466    | 1172 |

#### Conjunto test

| Estadística | Longitud (caracteres) | Número de palabras |
|-------------|----------------------:|-------------------:|
| Media       | 2359.44   | 352.71 |
| Desv. Est.  | 1111.03    | 163.39 |
| Mínimo      | 555    | 90 |
| Q1 (25%)    | 1546    | 236 |
| Mediana     | 2209    | 330 |
| Q3 (75%)    | 2962    | 443 |
| Máximo      | 6526    | 965 |

#### Conjunto validation

| Estadística | Longitud (caracteres) | Número de palabras |
|-------------|----------------------:|-------------------:|
| Media       | 2353.98   | 352.30 |
| Desv. Est.  | 1116.83    | 168.17 |
| Mínimo      | 498    | 69 |
| Q1 (25%)    | 1526    | 225 |
| Mediana     | 2220    | 328 |
| Q3 (75%)    | 2910    | 430 |
| Máximo      | 6010    | 956 |

### 2.2 Códigos CIE-10-ES (Etiquetas)

#### Conjunto train

| Estadística | Número de etiquetas por documento |
|-------------|----------------------------------:|
| Media       | 11.28 |
| Desv. Est.  | 6.95 |
| Mínimo      | 1 |
| Q1 (25%)    | 6 |
| Mediana     | 10 |
| Q3 (75%)    | 15 |
| Máximo      | 40 |

#### Conjunto test

| Estadística | Número de etiquetas por documento |
|-------------|----------------------------------:|
| Media       | 11.37 |
| Desv. Est.  | 6.59 |
| Mínimo      | 1 |
| Q1 (25%)    | 6 |
| Mediana     | 10 |
| Q3 (75%)    | 15 |
| Máximo      | 35 |

#### Conjunto validation

| Estadística | Número de etiquetas por documento |
|-------------|----------------------------------:|
| Media       | 10.71 |
| Desv. Est.  | 6.81 |
| Mínimo      | 1 |
| Q1 (25%)    | 5 |
| Mediana     | 10 |
| Q3 (75%)    | 14 |
| Máximo      | 33 |

#### Distribución General de Etiquetas

- **Número total de etiquetas**: 11,158
- **Número de códigos CIE-10 únicos**: 2,557

Las 10 etiquetas más frecuentes en todos los conjuntos:

| Código CIE-10 | Frecuencia | Porcentaje |
|---------------|------------|------------|
| r52 | 219 | 1.96% |
| r69 | 198 | 1.77% |
| r50.9 | 191 | 1.71% |
| i10 | 161 | 1.44% |
| r59.9 | 136 | 1.22% |
| r60.9 | 124 | 1.11% |
| r11.10 | 92 | 0.82% |
| r59.0 | 91 | 0.82% |
| b99.9 | 89 | 0.80% |
| r58 | 88 | 0.79% |

## 3. Análisis de Relaciones

### 3.1 Relación entre Longitud de Texto y Número de Etiquetas

El análisis de correlación muestra una relación positiva entre la longitud del texto clínico y el número de códigos CIE-10 asignados:

- Correlación entre longitud de texto (caracteres) y número de etiquetas: 0.5572
- Correlación entre número de palabras y número de etiquetas: 0.5284

Esta correlación sugiere que los textos más largos tienden a tener más diagnósticos asociados, lo cual es intuitivamente razonable ya que textos más extensos pueden describir casos más complejos con múltiples condiciones.

## 4. Comparación entre Conjuntos

### 4.1 Solapamiento de Etiquetas

#### train vs test

- Etiquetas únicas en train: 1,767
- Etiquetas únicas en test: 1,143
- Etiquetas comunes: 704
- Porcentaje de train presente en test: 39.84%
- Porcentaje de test presente en train: 61.59%
- Coeficiente de Jaccard: 0.3191

#### train vs validation

- Etiquetas únicas en train: 1,767
- Etiquetas únicas en validation: 1,158
- Etiquetas comunes: 731
- Porcentaje de train presente en validation: 41.37%
- Porcentaje de validation presente en train: 63.13%
- Coeficiente de Jaccard: 0.3332

#### test vs validation

- Etiquetas únicas en test: 1,143
- Etiquetas únicas en validation: 1,158
- Etiquetas comunes: 551
- Porcentaje de test presente en validation: 48.21%
- Porcentaje de validation presente en test: 47.58%
- Coeficiente de Jaccard: 0.3149

### 4.2 Características Comparativas

Los conjuntos de entrenamiento, validación y prueba muestran características generales similares en términos de:

1. **Distribución de longitud de texto**: Los tres conjuntos tienen distribuciones de longitud de texto comparables, lo que sugiere una división adecuada.
2. **Número de etiquetas por documento**: La distribución del número de códigos CIE-10 por documento es consistente entre los conjuntos.
3. **Diversidad de vocabulario**: Palabras similares aparecen con frecuencia comparable en los tres conjuntos.

## 5. Conclusiones y Recomendaciones

### 5.1 Principales Conclusiones

1. CODIESP presenta una distribución desigual de códigos CIE-10, con algunos códigos apareciendo con mucha mayor frecuencia que otros.
2. Existe una correlación positiva entre la longitud del texto clínico y el número de códigos asignados.
3. Los conjuntos de entrenamiento, validación y prueba mantienen características consistentes, lo que favorece el desarrollo de modelos de aprendizaje automático robustos.

### 5.2 Recomendaciones para el Artículo Científico

1. **Estrategia de modelado**: Considerar el desequilibrio de clases al diseñar modelos de clasificación multi-etiqueta.
2. **Evaluación**: Utilizar métricas que tengan en cuenta la distribución desigual de etiquetas (como F1 ponderado, precisión y recall por clase).
3. **Preprocesamiento**: Aplicar técnicas de normalización de texto específicas para documentos clínicos en español.
4. **Validación cruzada**: Complementar la evaluación con validación cruzada para obtener estimaciones más robustas del rendimiento.

## 6. Recursos Adicionales

Este análisis se ha realizado con Python utilizando las bibliotecas pandas, numpy, matplotlib, seaborn y NLTK. Los notebooks y scripts completos están disponibles en el proyecto CIE-10.

