# CSV Import Scripts

Lo primero ha sido entender como funciona la pagina con las herramientas de desarrollador, una vez identificado el patron que sigue sus endpoints, se ha procedido a hacer un script para cada tipo de información.

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
