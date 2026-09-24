#!/usr/bin/env python3
"""Tabla comparativa de los candidatos a promoción, medidos en el conjunto de prueba.

Lee los `model/eval_cand_*.json` (`make ai-eval-candidatos`) y, si existen, los
`model/rerank_cand_*.json` (`make ai-eval-candidatos-fusion`). Ordena por MAP fusionado cuando lo
hay, porque el modo fusionado es el que da el resultado titular del trabajo, y por MAP a secas en
caso contrario. El F1 va al lado porque no siempre se mueve en la misma dirección que el MAP.
"""

import glob
import json
from pathlib import Path


def main():
    base = Path(__file__).parent / "model"
    filas = []
    for ruta in sorted(glob.glob(str(base / "eval_cand_*.json"))):
        d = json.load(open(ruta, encoding="utf-8"))
        nombre = Path(ruta).stem.replace("eval_cand_", "")
        mejor = d.get("test_at_best", {})
        rer = base / f"rerank_cand_{nombre}.json"
        fusion = None
        if rer.exists():
            abl = json.loads(rer.read_text(encoding="utf-8")).get("ablacion", {})
            fusion = abl.get("solo_diccionario", {}).get("map_strict_test")
        filas.append(
            {
                "nombre": nombre,
                "map_strict": d.get("map_strict"),
                "map_fusion": fusion,
                "f1_micro": mejor.get("f1_micro"),
                "umbral": d.get("best_threshold_val"),
            }
        )

    if not filas:
        raise SystemExit("No hay eval_cand_*.json: ejecuta antes `make ai-eval-candidatos`.")

    def fmt(v, n=4):
        return f"{v:.{n}f}" if isinstance(v, (int, float)) else "n/d"

    # Se ordena por lo que decide la promoción: el modo fusionado si está medido para todos.
    clave = "map_fusion" if all(f["map_fusion"] is not None for f in filas) else "map_strict"
    filas.sort(key=lambda f: f[clave] or 0, reverse=True)
    print(f"\n{'modelo':<14}{'MAP':>9}{'MAP fusión':>12}{'F1 micro':>11}{'umbral val':>12}")
    print("-" * 58)
    for f in filas:
        print(
            f"{f['nombre']:<14}{fmt(f['map_strict']):>9}{fmt(f['map_fusion']):>12}"
            f"{fmt(f['f1_micro']):>11}{fmt(f['umbral'], 2):>12}"
        )
    print(f"\nOrdenado por {'MAP fusionado' if clave == 'map_fusion' else 'MAP sin diccionario'}.")

    lider = filas[0]
    prod = next((f for f in filas if f["nombre"] == "produccion"), None)
    if not prod:
        return
    if lider["nombre"] == "produccion":
        print("El modelo desplegado sigue siendo el mejor: no hay nada que promocionar.")
        return
    # Se declaran las dos diferencias: promocionar mirando solo una es como no mirar ninguna.
    for etiqueta, campo in (("MAP", clave), ("F1", "f1_micro")):
        a, b = lider.get(campo), prod.get(campo)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            print(
                f"'{lider['nombre']}' frente al desplegado: {(a - b) * 100:+.2f} pp de {etiqueta}."
            )


if __name__ == "__main__":
    main()
