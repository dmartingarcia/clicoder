"""Mide por qué la poda por grupos no compensa: cuán dispersa es la importancia.

Divide y vencerás solo gana si al tapar un grupo entero el logit no se mueve, porque entonces
descarta el subárbol completo. Un árbol binario sobre n palabras tiene 2n-1 nodos, así que sin
poda cuesta el doble que preguntar una por una. La pregunta empírica es cuántas palabras
superan el umbral: si son pocas, la poda dispara y gana; si son muchas, se paga el árbol entero.
"""

import string as _s

import numpy as np
import pandas as pd
import torch


def main():
    from classifier import CIE10Classifier, _CtxAtribucion

    clf = CIE10Classifier("/app/model")
    d = pd.read_csv("/data/codiesp_csvs/codiesp_D_source_test.csv")
    d.columns = d.columns.str.strip()
    textos = d.dropna(subset=["text"])["text"].astype(str).tolist()[:4]
    umbrales = [0.05, 0.1, 0.25, 0.5, 1.0]
    frac = {u: [] for u in umbrales}
    ns = []

    for texto in textos:
        preds = clf.predict(texto, top_k=5)
        codes = [int(clf.code_to_idx[p["code"]]) for p in preds if p["code"] in clf.code_to_idx]
        if not codes:
            continue
        enc = clf.tokenizer(texto, max_length=clf.config["max_length"], truncation=True)
        wpos = {}
        for pos, wid in enumerate(enc.word_ids()):
            if wid is not None:
                wpos.setdefault(wid, []).append(pos)
        raw = texto.split()
        cand = [w for w in wpos if w < len(raw) and len(raw[w].strip(_s.punctuation)) >= 4]
        ml = clf.config["max_length"]
        pad = clf.tokenizer.pad_token_id or 0
        ids = torch.tensor(
            [enc["input_ids"] + [pad] * (ml - len(enc["input_ids"]))], device=clf.device
        )
        msk = torch.tensor(
            [enc["attention_mask"] + [0] * (ml - len(enc["attention_mask"]))], device=clf.device
        )
        with torch.no_grad():
            base = clf.model(ids, msk)[0, codes].cpu()
        ctx = _CtxAtribucion(
            clf.model, ids, msk, clf.tokenizer.mask_token_id, wpos, codes, base, ml, 16
        )
        caidas = ctx.caida_al_enmascarar([[w] for w in cand])
        por_palabra = caidas.max(dim=1).values.numpy()  # efecto sobre el código que más mueve
        ns.append(len(cand))
        for u in umbrales:
            frac[u].append(float((por_palabra > u).mean()))

    n = int(np.mean(ns))
    print(f"palabras candidatas por informe: {n}")
    print(f"coste del exhaustivo: {n} evaluaciones · árbol binario completo: {2 * n - 1}")
    print(f"\n{'umbral':>8} {'% palabras que lo superan':>26} {'coste estimado de la poda':>27}")
    for u in umbrales:
        f = float(np.mean(frac[u]))
        m = max(f * n, 1)
        # nodos a visitar ~ 2*m*log2(n/m): los caminos hasta cada palabra relevante
        coste = min(2 * m * max(np.log2(n / m), 1), 2 * n - 1)
        print(f"{u:8.2f} {100 * f:25.1f}% {coste:26.0f}")


if __name__ == "__main__":
    main()
