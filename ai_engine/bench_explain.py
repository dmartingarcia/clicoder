"""Curva coste/fidelidad del método guiado por gradiente frente al exhaustivo.

La fidelidad se mide contra el exhaustivo, que es la referencia por construcción: mide el
efecto real de quitar cada palabra. Las listas se deduplican antes de comparar, porque una
palabra repetida en el informe aparece dos veces en el top-5 y hundiría el techo por debajo
de 1 sin que ningún método tenga la culpa.
Uso: python bench_explain.py [--device cpu|cuda]
"""

import argparse
import time

import numpy as np
import pandas as pd


def solape(a: list[str], b: list[str]) -> float:
    sa, sb = {x.lower() for x in a}, {x.lower() for x in b}
    return len(sa & sb) / max(len(sb), 1)


def main():
    from classifier import CIE10Classifier

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="cpu", help="cpu | cuda")
    args = ap.parse_args()

    clf = CIE10Classifier("/app/model", device=args.device)
    d = pd.read_csv("/data/codiesp_csvs/codiesp_D_source_test.csv")
    d.columns = d.columns.str.strip()
    textos = d.dropna(subset=["text"])["text"].astype(str).tolist()[:6]

    variantes = [("exhaustivo", "exhaustivo", {}), ("divide y venceras", "divide_y_venceras", {})]
    variantes += [(f"gradiente n={n}", "gradiente_filtrado", {"n": n}) for n in (16, 32, 64, 96)]
    variantes += [("diccionario", "diccionario", {})]

    # El diccionario no pasa por el encoder: sus términos son las frases que hicieron match, de
    # modo que su tiempo no depende del dispositivo. Si sus dependencias no están disponibles
    # (la imagen de entrenamiento no trae spaCy) se omite esa variante en vez de fallar.
    try:
        from baseline_dict import DictClassifier

        dic = DictClassifier("/app/model/baseline_dict.json")
        dic.predict("prueba")  # spaCy se carga de forma perezosa: hay que tocarlo aqui
    except Exception as exc:
        print(f"[aviso] variante 'diccionario' omitida: {exc}")
        dic = None
        variantes = [v for v in variantes if v[1] != "diccionario"]

    def explicar_diccionario(texto, codes, top_k=5):
        assert dic is not None
        por_bloque = {str(h.get("code", "")).upper()[:3]: h for h in dic.predict(texto)}
        idx_to_code = {i: c for c, i in clf.code_to_idx.items()}
        return {
            c: por_bloque.get(idx_to_code[c].upper()[:3], {}).get("matched_terms", [])[:top_k]
            for c in codes
        }

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
            if metodo == "diccionario":
                res = explicar_diccionario(texto, codes)
            else:
                res = clf.explain(texto, codes, top_k=5, method=metodo)
            dt = time.perf_counter() - t0
            if extra:
                C.METODOS_EXPLAIN["gradiente_filtrado"] = original
            if ref is None:
                ref = res
            acum[nombre]["t"].append(dt)
            acum[nombre]["ov"].append(np.mean([solape(res[c], ref[c]) for c in codes if ref[c]]))
            acum[nombre]["t1"].append(np.mean([res[c][:1] == ref[c][:1] for c in codes if ref[c]]))

    print(f"dispositivo: {args.device}")
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
