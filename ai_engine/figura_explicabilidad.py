#!/usr/bin/env python3
"""Genera la figura de ejemplo de explicabilidad a partir de un informe real.

Toma un informe del conjunto de prueba, predice sus códigos y resalta en el texto las palabras
que el enmascarado señala como responsables, con la intensidad proporcional a cuánto baja el
logit al quitarlas. Sale LaTeX, no una imagen: así el texto se puede leer y buscar en el PDF.

Salida: tfg/figs/ejemplo-explicabilidad.tex
"""

import argparse
import re
from pathlib import Path

import pandas as pd

from classifier import CIE10Classifier, load_code_descriptions

ESCAPES = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
}


def escapar(texto: str) -> str:
    return "".join(ESCAPES.get(c, c) for c in texto)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model_dir", default="/app/model")
    ap.add_argument("--test_file", default="/data/codiesp_csvs/codiesp_D_source_test.csv")
    ap.add_argument("--doc", type=int, default=0, help="Índice del informe a usar.")
    ap.add_argument("--max_palabras", type=int, default=90)
    ap.add_argument("--out", default="/app/../tfg/figs/ejemplo-explicabilidad.tex")
    args = ap.parse_args()

    clf = CIE10Classifier(args.model_dir)
    descripciones = load_code_descriptions(args.model_dir)
    df = pd.read_csv(args.test_file)
    df.columns = df.columns.str.strip()
    texto = " ".join(str(df.dropna(subset=["text"])["text"].iloc[args.doc]).split())
    texto = " ".join(texto.split()[: args.max_palabras])

    pred = clf.predict(texto, top_k=3, code_descriptions=descripciones)
    codigos = [p["code"] for p in pred if p["code"] in clf.code_to_idx]
    if not codigos:
        raise SystemExit("El informe elegido no produce ningún código; prueba con otro --doc.")

    idx = [int(clf.code_to_idx[c]) for c in codigos]
    triggers = clf.explain(texto, idx, top_k=6, with_scores=True)
    principal = idx[0]
    pesos = {palabra.lower(): float(peso) for palabra, peso in triggers[principal]}
    techo = max(pesos.values()) if pesos else 1.0

    # Tres niveles de sombreado: distinguir el término decisivo de los de apoyo dice más que
    # pintarlos todos igual, y no exige entender una escala continua.
    partes = []
    for palabra in texto.split():
        limpia = re.sub(r"[^\wáéíóúñü-]", "", palabra.lower())
        peso = pesos.get(limpia, 0.0)
        if peso <= 0:
            partes.append(escapar(palabra))
        else:
            nivel = 45 if peso >= techo * 0.66 else (28 if peso >= techo * 0.33 else 14)
            partes.append(f"\\colorbox{{amarillo!{nivel}}}{{{escapar(palabra)}}}")

    lista = ", ".join(
        f"\\emph{{{escapar(palabra)}}} ({float(peso):.2f})"
        for palabra, peso in triggers[principal][:5]
    )
    descripcion = escapar(str(pred[0].get("description", "") or ""))

    salida = f"""% Generado por ai_engine/figura_explicabilidad.py: no editar a mano.
\\begin{{figure}}[ht]
\\centering
\\fbox{{\\parbox{{0.93\\textwidth}}{{\\footnotesize\\setlength{{\\baselineskip}}{{13pt}}
{" ".join(partes)}
}}}}
\\caption[Ejemplo de explicabilidad sobre un informe real]{{Términos que sostienen la predicción
del código \\texttt{{{escapar(codigos[0])}}} ({descripcion}) sobre un informe del conjunto de
prueba. El sombreado es proporcional a la caída del \\emph{{logit}} al enmascarar cada palabra,
en tres niveles. Los cinco primeros: {lista}.}}
\\label{{fig:ejemplo-explicabilidad}}
\\end{{figure}}
"""
    destino = Path(args.out).resolve()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(salida, encoding="utf-8")
    print(f"[figura] {destino}")
    print(f"[figura] codigo={codigos[0]} terminos={[p for p, _ in triggers[principal][:5]]}")


if __name__ == "__main__":
    main()
