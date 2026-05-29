#!/usr/bin/env python3
"""
Generador de reporte completo de análisis de datos CIE-10 y CodiESP.
Ejecuta los notebooks existentes, extrae visualizaciones y genera un reporte markdown consolidado.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
import base64

# Configuración
NOTEBOOKS = [
    {
        "file": "codiesp_analisis_estadistico.ipynb",
        "title": "Análisis Estadístico CodiESP",
        "description": "Análisis del corpus de textos clínicos CodiESP (train/val/test)"
    },
    {
        "file": "cie10_analisis_estadistico.ipynb",
        "title": "Análisis Catálogo CIE-10",
        "description": "Exploración de los códigos CIE-10 (diagnósticos, procedimientos, químicos)"
    },
    {
        "file": "cie10_spacy_word_analysis.ipynb",
        "title": "Análisis Lingüístico con SpaCy",
        "description": "Análisis morfosintáctico y validación de vocabulario médico"
    },
    {
        "file": "analisis_linguistico_jerarquico.ipynb",
        "title": "Análisis Jerárquico de Términos",
        "description": "Análisis de n-gramas y patrones lingüísticos por capítulos CIE-10"
    }
]

OUTPUT_DIR = Path("report_output")
IMAGES_DIR = OUTPUT_DIR / "images"
REPORT_FILE = OUTPUT_DIR / "REPORTE_COMPLETO_ANALISIS.md"


def setup_directories():
    """Crea directorios de salida si no existen."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    IMAGES_DIR.mkdir(exist_ok=True)
    print(f"Directorios creados: {OUTPUT_DIR}, {IMAGES_DIR}")


def execute_notebook(notebook_path, timeout=600):
    """Ejecuta un notebook y devuelve el notebook ejecutado."""
    print(f"\n{'='*80}")
    print(f"Ejecutando: {notebook_path}")
    print(f"{'='*80}")

    try:
        with open(notebook_path, 'r', encoding='utf-8') as f:
            nb = nbformat.read(f, as_version=4)

        ep = ExecutePreprocessor(timeout=timeout, kernel_name='python3')
        ep.preprocess(nb, {'metadata': {'path': './'}})

        print(f"OK: Notebook ejecutado: {notebook_path}")
        return nb
    except Exception as e:
        print(f"ERROR ejecutando {notebook_path}: {e}")
        return None


def extract_images_from_notebook(nb, notebook_name):
    """Extrae imágenes del notebook ejecutado."""
    image_paths = []
    if nb is None:
        return image_paths

    img_counter = 0
    for cell in nb.cells:
        if cell.cell_type == 'code' and 'outputs' in cell:
            for output in cell.outputs:
                img_data = None
                img_format = None

                if output.get('output_type') in ['display_data', 'execute_result']:
                    data = output.get('data', {})
                    if 'image/png' in data:
                        img_data = data['image/png']
                        img_format = 'png'
                    elif 'image/jpeg' in data:
                        img_data = data['image/jpeg']
                        img_format = 'jpg'

                if img_data:
                    img_counter += 1
                    img_filename = f"{notebook_name}_fig{img_counter}.{img_format}"
                    img_path = IMAGES_DIR / img_filename

                    with open(img_path, 'wb') as f:
                        f.write(base64.b64decode(img_data))

                    image_paths.append(img_path)
                    print(f"  -> Imagen extraída: {img_filename}")

    print(f"Imágenes extraídas: {img_counter}")
    return image_paths


def extract_summary_stats(nb):
    """Extrae estadísticas clave del notebook."""
    stats = []
    if nb is None:
        return stats

    for cell in nb.cells:
        if cell.cell_type == 'code' and 'outputs' in cell:
            for output in cell.outputs:
                if output.get('output_type') in ['stream', 'execute_result']:
                    text = output.get('text', '')
                    if not text and 'data' in output:
                        text = output['data'].get('text/plain', '')

                    if text and isinstance(text, (str, list)):
                        if isinstance(text, list):
                            text = ''.join(text)
                        if any(p in text.lower() for p in ['mean', 'median', 'total', 'unique', '%']):
                            stats.append(text.strip())

    return stats[:15]


def generate_markdown_report(results):
    """Genera el reporte markdown consolidado."""
    print(f"\n{'='*80}")
    print("Generando reporte markdown...")
    print(f"{'='*80}")

    md = f"""# Reporte Completo de Análisis de Datos CIE-10

**Fecha**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Resumen Ejecutivo

| Dataset | Registros |
|---------|-----------|
| CodiESP Train | 500 |
| CodiESP Validation | 250 |
| CodiESP Test | 250 |
| CIE-10 Diagnósticos | 101,246 |

---

"""

    for result in results:
        md += f"## {result['title']}\n\n"
        md += f"**Notebook**: `{result['notebook']}`\n\n"

        if result['success']:
            md += "Ejecutado exitosamente\n\n"

            if result['stats']:
                md += "### Estadísticas\n\n```\n"
                for stat in result['stats'][:8]:
                    md += stat + "\n"
                md += "```\n\n"

            if result['images']:
                md += "### Visualizaciones\n\n"
                for img_path in result['images']:
                    rel_path = img_path.relative_to(OUTPUT_DIR)
                    md += f"![{img_path.stem}]({rel_path})\n\n"
        else:
            md += f"Error: {result.get('error', 'Desconocido')}\n\n"

        md += "---\n\n"

    md += """## Conclusiones

1. **Desequilibrio severo**: Distribución power-law en códigos
2. **Cobertura parcial**: ~50% códigos CIE-10 en CodiESP
3. **Multi-label**: Media ~11 códigos/documento
4. **Splits consistentes**: Jaccard ~0.31-0.33

"""

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(md)

    print(f"Reporte: {REPORT_FILE}")


def main():
    print("="*80)
    print("GENERADOR DE REPORTE CIE-10")
    print("="*80)

    setup_directories()
    results = []

    for nb_config in NOTEBOOKS:
        nb_file = Path(nb_config['file'])

        if not nb_file.exists():
            print(f"No encontrado: {nb_file}")
            results.append({
                'notebook': nb_file.name,
                'title': nb_config['title'],
                'success': False,
                'error': f'Archivo no encontrado',
                'images': [],
                'stats': []
            })
            continue

        nb = execute_notebook(nb_file, timeout=600)
        success = nb is not None

        images = []
        stats = []
        if nb:
            images = extract_images_from_notebook(nb, nb_file.stem)
            stats = extract_summary_stats(nb)

        results.append({
            'notebook': nb_file.name,
            'title': nb_config['title'],
            'success': success,
            'error': None if success else f"Error ejecutando {nb_file.name}",
            'images': images,
            'stats': stats
        })

    generate_markdown_report(results)
    print("\nProceso completado")


if __name__ == "__main__":
    main()
