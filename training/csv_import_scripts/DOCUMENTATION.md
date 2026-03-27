# CSV Import Scripts

## Motivación y contexto

Este trabajo forma parte de un Trabajo de Fin de Grado (TFG) cuyo objetivo es desarrollar un sistema de codificación automática de diagnósticos clínicos en español mediante técnicas de procesamiento del lenguaje natural (PLN). El sistema debe, dada una nota clínica en texto libre, predecir los códigos CIE-10 que corresponden a los diagnósticos documentados.

Para abordar este problema se necesitan dos recursos fundamentales:

1. **Corpus etiquetado**: el dataset CodiESP (Clinical Case Reports in Spanish), utilizado como conjunto de entrenamiento y evaluación.

2. **Diccionario CIE-10 en español**: la lista completa de códigos con sus descripciones clínicas oficiales en castellano.

El diccionario oficial en español **no está disponible como descarga pública estructurada**. La única fuente oficial es el portal [eCIE-maps](https://www.eciemaps.sanidad.gob.es/) del Ministerio de Sanidad, que expone los datos a través de una API web no documentada. Por ello se desarrollaron los scripts de scraping recogidos en este directorio, que consultan sistemáticamente dicha API para obtener el diccionario completo.

### Aplicaciones del diccionario en el proyecto

### 1. Entrenamiento del clasificador neuronal (`train.py`)

El fichero `cie10-es-diagnoses.csv` alimenta el pipeline de entrenamiento de dos formas:

- Define el espacio de clases del clasificador (bloques de 3 caracteres, ~809 categorías).
- Proporciona las descripciones en español asociadas a cada código, que el modelo puede utilizar para enriquecer su representación semántica.

### 2. Sistema de baseline por diccionario (`baseline_dict.py`)

Los tres CSVs generados permiten construir un sistema de referencia no supervisado que detecta menciones directas de términos médicos en el texto:

- `cie10-es-diagnoses.csv` — detecta descripciones de diagnósticos en la nota clínica.
- `cie10-es-procedures.csv` — detecta menciones de procedimientos.
- `cie10-es-chemicals.csv` — detecta nombres de fármacos o sustancias, mapeándolos al bloque de intoxicación o efecto adverso correspondiente (T36–T65).

Estos baselines sirven como cota inferior de referencia: cualquier modelo supervisado debe superar sus resultados para justificar la complejidad adicional que introduce.

### 3. Punto de comparación con el estado del arte

En la competición CodiESP 2020, el mejor sistema basado en diccionario obtuvo un F1 de 0.687 sobre códigos completos. Este trabajo opera sobre bloques de 3 caracteres, lo que hace que los números no sean directamente comparables, pero permite situar los resultados en el contexto de la literatura.

---

Lo primero ha sido entender cómo funciona la página con las herramientas de desarrollador del navegador. Una vez identificado el patrón que siguen sus endpoints, se procedió a implementar un script para cada tipo de información.

## Jerarquía de los Endpoints

La API de eCIE-maps ([www.eciemaps.sanidad.gob.es](https://www.eciemaps.sanidad.gob.es/)) está estructurada con una jerarquía clara que permite acceder a diferentes tipos de datos médicos. La estructura de los endpoints varía según el tipo de información que queremos recuperar:

### 1. Diagnósticos (CIE-10-MC)

Los diagnósticos siguen una estructura jerárquica basada en el código alfanumérico de la CIE-10:

```text
https://www.eciemaps.sanidad.gob.es/cie10mc/2024/lt/sec/{LETRA}{NÚMERO}
```

Donde:

- **LETRA**: Una letra del alfabeto (A-Z) que representa la categoría principal de la enfermedad.
- **NÚMERO**: Un dígito de 0 a 9 que permite segmentar la categoría.

Por ejemplo:

- `https://www.eciemaps.sanidad.gob.es/cie10mc/2024/lt/sec/A0` - Enfermedades infecciosas intestinales
- `https://www.eciemaps.sanidad.gob.es/cie10mc/2024/lt/sec/I2` - Enfermedades isquémicas del corazón

### 2. Sustancias Químicas (Fármacos)

Los datos de sustancias químicas/fármacos están organizados por letra inicial:

```text
https://www.eciemaps.sanidad.gob.es/cie10mc/2024/ia/drugsByLetter/{LETRA}
```

Donde:

- **LETRA**: Puede ser cualquier letra del alfabeto (0, A-Z).

### 3. Procedimientos (CIE-10-PCS)

Los procedimientos médicos siguen una estructura jerárquica de 3 niveles:

#### Nivel 1 - Secciones principales

```text
https://www.eciemaps.sanidad.gob.es/cie10pcs/2024/tab/t1
```

#### Nivel 2 - Subsecciones

```text
https://www.eciemaps.sanidad.gob.es/cie10pcs/2024/tab/t2/{CÓDIGO_T1}
```

Donde:

- **CÓDIGO_T1**: Código obtenido del nivel T1.

#### Nivel 3 - Procedimientos específicos

```text
https://www.eciemaps.sanidad.gob.es/cie10pcs/2024/tab/t3/{CÓDIGO_T2}
```

Donde:

- **CÓDIGO_T2**: Código obtenido del nivel T2.

#### Tablas detalladas de procedimientos

```text
https://www.eciemaps.sanidad.gob.es/cie10pcs/2024/lt/table/{CÓDIGO_T3}
```

Donde:

- **CÓDIGO_T3**: Código obtenido del nivel T3.

#### Información específica de un procedimiento

```text
https://www.eciemaps.sanidad.gob.es/ref/cie10pcs/{CÓDIGO_COMPLETO}
```

Donde:

- **CÓDIGO_COMPLETO**: Código de 7 caracteres que identifica un procedimiento específico.

### 4. Códigos específicos (Nodos finales)

Para información detallada sobre un código específico cuando se identifica como un nodo final:

```text
https://www.eciemaps.sanidad.gob.es/cie10mc/2024/ia/children/{ID}
```

Donde:

- **ID**: Identificador único del nodo.

## Estrategia de Extracción

La estrategia utilizada para extraer los datos consiste en:

1. Comenzar con los niveles superiores de la jerarquía.
2. Iterar a través de cada categoría de nivel superior.
3. Para cada categoría, recuperar subcategorías o datos específicos.
4. En el caso de los procedimientos, construir combinaciones de los diferentes ejes (localización, abordaje, dispositivo y calificador).

Esta estructura jerárquica permite una exploración sistemática y exhaustiva de todos los códigos médicos disponibles en el sistema eCIE-maps.

## Consideraciones Técnicas

Para acceder a los datos de la API, se han implementado las siguientes estrategias técnicas:

1. **Simulación de navegador web**: Es necesario imitar las cabeceras HTTP de un navegador web para evitar que el servidor bloquee las peticiones con un código HTTP 403 - Forbidden.

2. **Peticiones asíncronas**: Se utiliza la biblioteca `grequests` para realizar múltiples peticiones en paralelo, lo que optimiza el tiempo de extracción de datos.

3. **Procesamiento por lotes**: Para evitar problemas de memoria en el caso de los procedimientos (más de 75,000 códigos), se procesan los datos en lotes más pequeños.

4. **Manejo de estructuras anidadas**: La información se extrae navegando a través de estructuras jerárquicas de datos JSON, mapeando las relaciones entre diferentes niveles.

5. **Visualización del progreso**: Se han implementado barras de progreso para visualizar el avance de la extracción de datos, especialmente útil en procedimientos que requieren un tiempo considerable.
