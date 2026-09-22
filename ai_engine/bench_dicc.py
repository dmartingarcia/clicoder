"""Latencia y fidelidad del método `diccionario` frente al exhaustivo.

El diccionario no usa el encoder: devuelve las frases que hicieron coincidencia por regex.
Es instantáneo, pero explica el BLOQUE y no el código, y devuelve frases en vez de palabras
sueltas, así que el solape con el exhaustivo mide algo distinto que entre los otros métodos:
no cuánta fidelidad pierde, sino cuánto se parecen dos formas distintas de justificar.
"""

import time

import numpy as np
import pandas as pd


def main():
    from baseline_dict import DictClassifier
    from classifier import CIE10Classifier

    clf = CIE10Classifier("/app/model")
    dic = DictClassifier("/app/model/baseline_dict.json")
    d = pd.read_csv("/data/codiesp_csvs/codiesp_D_source_test.csv")
    d.columns = d.columns.str.strip()
    textos = d.dropna(subset=["text"])["text"].astype(str).tolist()[:6]

    t_dic, t_exh, cobertura, solape_palabras = [], [], [], []
    for texto in textos:
        preds = clf.predict(texto, top_k=5)
        codigos = [p["code"] for p in preds if p["code"] in clf.code_to_idx]
        if not codigos:
            continue
        a = time.perf_counter()
        hits = dic.predict(texto)
        t_dic.append(time.perf_counter() - a)
        por_bloque = {str(h.get("code", "")).upper()[:3]: h.get("matched_terms", []) for h in hits}
        terminos_dic = {c: por_bloque.get(c.upper()[:3], []) for c in codigos}
        cobertura.append(np.mean([1.0 if terminos_dic[c] else 0.0 for c in codigos]))

        idx = [int(clf.code_to_idx[c]) for c in codigos]
        a = time.perf_counter()
        exh = clf.explain(texto, idx, top_k=5, method="exhaustivo")
        t_exh.append(time.perf_counter() - a)
        # ¿Aparece alguna palabra del modelo dentro de las frases del diccionario?
        sol = []
        for c in codigos:
            palabras = {w.lower() for w in exh.get(int(clf.code_to_idx[c]), [])}
            frases = " ".join(terminos_dic[c]).lower()
            sol.append(
                np.mean([1.0 if w in frases else 0.0 for w in palabras]) if palabras else 0.0
            )
        solape_palabras.append(np.mean(sol))

    print(f"diccionario   {np.mean(t_dic):7.3f} s   cobertura de códigos: {np.mean(cobertura):.0%}")
    print(f"exhaustivo    {np.mean(t_exh):7.3f} s")
    print(f"factor de aceleración: {np.mean(t_exh) / max(np.mean(t_dic), 1e-9):.0f}x")
    print(
        f"palabras del modelo contenidas en las frases del diccionario: {np.mean(solape_palabras):.0%}"
    )


if __name__ == "__main__":
    main()
