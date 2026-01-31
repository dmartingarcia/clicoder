# Análisis Estadístico de Ficheros CIE-10-ES y CODIESP

## Resumen Ejecutivo

Este documento presenta un análisis estadístico detallado de los conjuntos de datos CIE-10-ES (diagnósticos, procedimientos y productos químicos) y CODIESP. El objetivo es comprender la distribución y características de estos datos para su uso en un artículo científico.

Fecha de análisis: 15 de October de 2025

## 1. Descripción General de los Datos

### 1.1 Conjuntos de Datos Analizados

| Dataset | Registros | Columnas |
|---------|-----------|----------|
| CIE-10-ES Diagnósticos | 101,246 | 13 |
| CIE-10-ES Procedimientos | 78,496 | 13 |
| CIE-10-ES Químicos | 5,050 | 20 |
| CODIESP Train | 500 | 4 |
| CODIESP Test | 250 | 4 |
| CODIESP Validation | 250 | 4 |

### 1.2 Estructura de los Datos

#### CIE-10-ES Diagnósticos
- **Columnas principales**: code, description, perinatal, pediatric, maternity, adult, poaExempt, noPrincipal, exclusiveGender, vcdp
- **Formato de código**: Alfanumérico, con una letra inicial que indica la categoría principal

#### CIE-10-ES Procedimientos
- **Columnas principales**: code, class_name, subclass_name, procedure, procedure_definition, localization, approach, device, calification, definition, description, timesSelected, gender
- **Organización**: Jerarquía de clases y subclases de procedimientos

#### CIE-10-ES Químicos
- **Columnas principales**: area, code1-code6, description, fatherId, finalNode, id, level, notes
- **Características**: Múltiples códigos para un mismo producto químico

#### CODIESP
- **Estructura**: Texto clínico y etiquetas asociadas (códigos CIE-10)
- **Conjuntos**: Train, Test y Validation para tareas de aprendizaje automático

## 2. Hallazgos Principales

### 2.1 Distribución de Categorías en Diagnósticos CIE-10-ES

Las categorías principales de diagnósticos (primera letra del código) muestran una distribución desigual, con algunas categorías dominantes:

- Las categorías más frecuentes son: ('R', 'S', 'T', 'I', 'M') (diagnósticos relacionados con síntomas, lesiones, envenenamientos y ciertas enfermedades infecciosas y del sistema musculoesquelético)
- Las categorías menos frecuentes son: ('U', 'Y', 'X') (códigos especiales y causas externas)

### 2.2 Características de los Procedimientos CIE-10-ES

- **Clases de procedimientos**: La distribución muestra una concentración en procedimientos médico-quirúrgicos
- **Tipos de abordaje**: Predominan los abordajes ('Abierto', 'Percutáneo', 'Endoscópico Percutáneo')
- **Frecuencia de selección**: Existe una alta variabilidad en el número de veces que se selecciona cada procedimiento

### 2.3 Análisis de Productos Químicos CIE-10-ES

- **Múltiples códigos**: 96.8% de los productos químicos tienen al menos 2 códigos asociados
- **Distribución por categorías**: Los códigos T predominan en los productos químicos, indicando su relación con envenenamientos y efectos tóxicos

### 2.4 Características de los Datos CODIESP

- **Longitud de textos**: Los textos clínicos tienen una longitud media variable entre conjuntos
- **Distribución de etiquetas**: Se observa una distribución de ley de potencia, con pocas etiquetas muy frecuentes y muchas poco frecuentes
- **Cobertura de códigos**: ?% de las etiquetas CODIESP corresponden a códigos presentes en el dataset de diagnósticos CIE-10-ES

## 3. Comparaciones entre Ficheros

### 3.1 Relación entre Diagnósticos y Productos Químicos

- Existen categorías comunes entre diagnósticos y productos químicos, principalmente en categorías relacionadas con envenenamientos y efectos tóxicos
- La distribución de estas categorías comunes muestra patrones diferentes en cada conjunto de datos

### 3.2 Correspondencia entre CODIESP y CIE-10-ES

- Las etiquetas en CODIESP representan un subconjunto de los códigos disponibles en CIE-10-ES Diagnósticos
- La distribución de frecuencia de estas etiquetas difiere de la distribución general en el conjunto completo de códigos

## 4. Conclusiones y Recomendaciones

### 4.1 Principales Conclusiones

1. Los conjuntos de datos CIE-10-ES tienen estructuras diferentes pero complementarias
2. Existe un desequilibrio significativo en la distribución de categorías en todos los conjuntos
3. Los datos CODIESP ofrecen un valioso conjunto de textos clínicos etiquetados, aunque con una cobertura parcial de los códigos CIE-10-ES

### 4.2 Recomendaciones para el Artículo Científico

1. **Representatividad**: Considerar el desequilibrio de clases en cualquier modelo de aprendizaje automático
2. **Integración**: Aprovechar la complementariedad entre los conjuntos de datos para tareas de PLN médico
3. **Evaluación**: Diseñar métricas que tengan en cuenta la jerarquía de códigos CIE-10-ES
4. **Preprocesamiento**: Normalizar las descripciones y textos para manejar la variabilidad en longitud y formato

## 5. Recursos Adicionales

Este análisis se ha realizado con Python utilizando las bibliotecas pandas, numpy, matplotlib y seaborn. Los notebooks y scripts completos están disponibles en el proyecto CIE-10.

