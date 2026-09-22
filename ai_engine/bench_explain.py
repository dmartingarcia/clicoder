"""Curva coste/fidelidad del método guiado por gradiente frente al exhaustivo.

La fidelidad se mide contra el exhaustivo, que es la referencia por construcción: mide el
efecto real de quitar cada palabra. Las listas se deduplican antes de comparar, porque una
palabra repetida en el informe aparece dos veces en el top-5 y hundiría el techo por debajo
de 1 sin que ningún método tenga la culpa.
"""

import time

import numpy as np
import pandas as pd


def solape(a: list[str], b: list[str]) -> float:
    sa, sb = {x.lower() for x in a}, {x.lower() for x in b}
    return len(sa & sb) / max(len(sb), 1)


def main():
    from classifier import CIE10Classifier

    clf = CIE10Classifier("/app/model")
    d = pd.read_csv("/data/codiesp_csvs/codiesp_D_source_test.csv")
    d.columns = d.columns.str.strip()
    textos = d.dropna(subset=["text"])["text"].astype(str).tolist()[:6]

    variantes = [("exhaustivo", "exhaustivo", {})]
    variantes += [(f"gradiente n={n}", "gradiente_filtrado", {"n": n}) for n in (16, 32, 64, 96)]
    acum = {nombre: {"t": [], "ov": [], "t1": []} for nombre, _, _ in variantes}

    for texto in textos:
        preds = clf.predict(texto, top_k=5)
        codes = [int(clf.code_to_idx[p["code"]]) for p in preds if p["code"] in clf.code_to_idx]
        if not codes:
            continue
        ref = None
        for nombre, metodo, extra in variantes:
            if extra:
                import classifier as C

                original = C.METODOS_EXPLAIN["gradiente_filtrado"]
                C.METODOS_EXPLAIN["gradiente_filtrado"] = lambda ctx, cand, n=extra["n"]: (
                    C._explicar_gradiente_filtrado(ctx, cand, n)
                )
            t0 = time.perf_counter()
            res = clf.explain(texto, codes, top_k=5, method=metodo)
            dt = time.perf_counter() - t0
            if extra:
                C.METODOS_EXPLAIN["gradiente_filtrado"] = original
            if ref is None:
                ref = res
            acum[nombre]["t"].append(dt)
            acum[nombre]["ov"].append(np.mean([solape(res[c], ref[c]) for c in codes if ref[c]]))
            acum[nombre]["t1"].append(np.mean([res[c][:1] == ref[c][:1] for c in codes if ref[c]]))

    print(f"{'variante':18} {'seg':>7} {'x mas rapido':>13} {'solape@5':>9} {'nº1 igual':>10}")
    base = np.mean(acum["exhaustivo"]["t"])
    for nombre, _, _ in variantes:
        a = acum[nombre]
        print(
            f"{nombre:18} {np.mean(a['t']):7.2f} {base / np.mean(a['t']):13.1f} "
            f"{np.mean(a['ov']):9.2f} {np.mean(a['t1']):10.2f}"
        )


if __name__ == "__main__":
    main()
