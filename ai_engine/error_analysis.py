#!/usr/bin/env python3
"""Clasifica los errores del modelo sobre el conjunto de prueba.

Un F1 dice cuánto falla; esto dice en qué falla. Cada falso positivo y cada falso negativo
se etiqueta según su distancia al código correcto: mismo bloque de tres caracteres (error de
especificidad), mismo capítulo pero otro bloque, o capítulo distinto (error de comprensión).

Salida: model/error_analysis.json
"""

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import torch

from classifier import CIE10Classifier, _extract_chapter
from eval_test import _infer, _load

BLOQUE = slice(0, 3)


def _clasifica(codigo: str, gold: set[str]) -> str:
    """Distancia del código a lo que el documento tenía anotado."""
    if any(g[BLOQUE] == codigo[BLOQUE] for g in gold):
        return "mismo_bloque"
    cap = _extract_chapter(codigo)
    if cap and any(_extract_chapter(g) == cap for g in gold):
        return "mismo_capitulo"
    return "otro_capitulo"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model_dir", default=str(Path(__file__).parent / "model"))
    ap.add_argument("--test_file", default="/data/codiesp_csvs/codiesp_D_source_test.csv")
    ap.add_argument("--threshold", type=float, default=0.3)
    ap.add_argument("--batch_size", type=int, default=8)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    clf = CIE10Classifier(args.model_dir, device=device)
    idx_to_code = {i: c for c, i in clf.code_to_idx.items()}
    full_codes = bool(clf.config.get("full_codes", True))
    max_length = int(clf.config.get("max_length", 512))

    texts, _T, _ntot, _nreach, _unseen, gold_lists = _load(
        args.test_file, clf.code_to_idx, len(clf.code_to_idx), full_codes
    )
    probs = _infer(clf, texts, max_length, args.batch_size)

    fp = Counter()
    fn = Counter()
    n_pred = n_gold = 0
    fp_por_codigo = Counter()
    fn_por_codigo = Counter()

    for i, gold in enumerate(gold_lists):
        gold = {g for g in gold}
        pred = {idx_to_code[j] for j in np.where(probs[i] >= args.threshold)[0]}
        n_pred += len(pred)
        n_gold += len(gold)

        for c in pred - gold:
            fp[_clasifica(c, gold)] += 1
            fp_por_codigo[c] += 1
        for c in gold - pred:
            fn[_clasifica(c, pred)] += 1
            fn_por_codigo[c] += 1

    # "otro_capitulo" mide el mismo fallo en los dos sentidos, pero un falso negativo en un
    # documento sin ninguna predicción cercana no es comparable: se anota aparte.
    total_fp, total_fn = sum(fp.values()), sum(fn.values())
    salida = {
        "threshold": args.threshold,
        "n_docs": len(texts),
        "codigos_por_documento": {
            "predichos": round(n_pred / len(texts), 2),
            "anotados": round(n_gold / len(texts), 2),
        },
        "falsos_positivos": {
            "total": total_fp,
            **{k: {"n": v, "pct": round(100 * v / max(1, total_fp), 1)} for k, v in fp.items()},
        },
        "falsos_negativos": {
            "total": total_fn,
            **{k: {"n": v, "pct": round(100 * v / max(1, total_fn), 1)} for k, v in fn.items()},
        },
        "top_falsos_positivos": fp_por_codigo.most_common(15),
        "top_falsos_negativos": fn_por_codigo.most_common(15),
    }

    out = args.out or str(Path(args.model_dir) / "error_analysis.json")
    Path(out).write_text(json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(salida, indent=2, ensure_ascii=False))
    print(f"\n[error_analysis] escrito en {out}")


if __name__ == "__main__":
    main()
