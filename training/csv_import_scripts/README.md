# Scripts de Importación CSV para CIE-10

Este directorio contiene un conjunto de scripts para extraer y procesar datos de la Clasificación Internacional de Enfermedades (CIE-10) desde la API oficial de eCIE-maps. Los scripts están diseñados para recopilar diagnósticos, procedimientos, sustancias químicas y conjuntos de datos CODIESP relacionados con la CIE-10.

## Contenido del Directorio

- **Scripts de Extracción**:
  - `collect_diagnoses.py`: Extrae códigos de diagnóstico CIE-10-MC.
  - `collect_procedures.py`: Extrae códigos de procedimientos CIE-10-PCS.
  - `collect_chemicals.py`: Extrae códigos de sustancias químicas/fármacos.
  - `collect_codiesp_dataset.py`: Descarga y procesa el dataset CODIESP para NLP.

- **Archivos de Soporte**:
  - `Makefile`: Automatiza la ejecución de scripts y gestión del entorno.
  - `requirements.txt`: Dependencias de Python necesarias.
  - `DOCUMENTATION.md`: Documentación técnica detallada sobre la API y metodología.

- **Archivos CSV Generados**:
  - `cie10-es-diagnoses.csv`: Códigos de diagnóstico CIE-10.
  - `cie10-es-procedures.csv`: Códigos de procedimientos CIE-10-PCS.
  - `cie10-es-chemicals.csv`: Códigos de sustancias químicas/fármacos.
  - `codiesp_csvs/`: Directorio con archivos CSV del dataset CODIESP.

## Uso del Makefile

El proyecto incluye un Makefile para facilitar la automatización de tareas comunes. Permite gestionar el entorno virtual de Python y ejecutar los scripts de recolección de datos.

### Comandos Disponibles

```bash
# Crear entorno virtual e instalar dependencias
make venv

# Ejecutar scripts individuales
make collect_diagnoses
make collect_procedures
make collect_chemicals
make collect_codiesp

# Ejecutar todos los scripts en secuencia
make all

# Limpiar el entorno virtual
make clean
```

### Estructura del Makefile

El Makefile está organizado en secciones:

1. **Configuración del entorno**: Define variables para el entorno virtual y comandos Python.
2. **Creación del entorno virtual**: Crea un entorno aislado e instala dependencias.
3. **Ejecución de scripts individuales**: Comandos para ejecutar cada script por separado.
4. **Ejecución completa**: Comando para ejecutar todos los scripts en secuencia.
5. **Limpieza**: Comando para eliminar el entorno virtual.

## Documentación Técnica

El archivo `DOCUMENTATION.md` proporciona información detallada sobre:

### Jerarquía de los Endpoints

La documentación explica la estructura jerárquica de la API de eCIE-maps:

- **Diagnósticos (CIE-10-MC)**: Organización por letras (A-Z) y números (0-9).
- **Sustancias Químicas**: Organización alfabética.
- **Procedimientos (CIE-10-PCS)**: Sistema jerárquico de 3 niveles (T1, T2, T3).
- **Códigos específicos**: Acceso a nodos finales con información detallada.

### Estrategia de Extracción

Se detalla la metodología utilizada para extraer los datos, comenzando por los niveles superiores de la jerarquía y descendiendo hasta los datos específicos.

### Consideraciones Técnicas

La documentación incluye aspectos técnicos importantes:

- Simulación de cabeceras HTTP para evitar bloqueos.
- Uso de peticiones asíncronas para optimizar el tiempo de extracción.
- Procesamiento por lotes para manejar grandes volúmenes de datos.
- Manejo de estructuras JSON anidadas.
- Visualización del progreso mediante barras de progreso.

## Requisitos

- Python 3.6 o superior
- Bibliotecas de Python especificadas en `requirements.txt`
- Conexión a Internet para acceder a la API de eCIE-maps

## Notas Importantes

- La extracción de datos puede llevar tiempo, especialmente para procedimientos (más de 75,000 códigos).
- Los scripts verifican si los archivos CSV ya existen antes de iniciar una nueva extracción.
- Se requiere simulación de cabeceras HTTP para evitar el bloqueo por parte del servidor.
