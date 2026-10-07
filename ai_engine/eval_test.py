# Umbral global elegido sobre VALIDACIÓN y reutilizado en TEST: elegirlo sobre test sería tuning
# sobre el conjunto de evaluación.

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
)

from classifier import CIE10Classifier, _extract_chapter
from train import parse_labels


def _infer(clf, texts, max_length, batch_size):
    """Probabilidades (n_docs, num_codes) en orden de índice del modelo."""
    num_codes = len(clf.code_to_idx)
    probs = np.zeros((len(texts), num_codes), dtype=np.float32)
    model, tok, device = clf.model, clf.tokenizer, clf.device
    model.eval()
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            enc = tok(
                chunk,
                max_length=max_length,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )
            logits = model(enc["input_ids"].to(device), enc["attention_mask"].to(device))
            probs[i : i + len(chunk)] = torch.sigmoid(logits).float().cpu().numpy()
            print(f"  {min(i + len(chunk), len(texts))}/{len(texts)}", end="\r")
    print()
    return probs


def _build_gold(gold_lists, code_to_idx, num_codes):
    """Devuelve T (alcanzable), n_total y n_reach por documento, y códigos fuera de vocab."""
    T = np.zeros((len(gold_lists), num_codes), dtype=np.int8)
    n_total = np.zeros(len(gold_lists), dtype=np.int32)
    n_reach = np.zeros(len(gold_lists), dtype=np.int32)
    unseen = set()
    for r, codes in enumerate(gold_lists):
        for c in dict.fromkeys(codes):
            n_total[r] += 1
            idx = code_to_idx.get(c)
            if idx is not None:
                T[r, idx] = 1
                n_reach[r] += 1
            else:
                unseen.add(c)
    return T, n_total, n_reach, unseen


def _f1(T, probs, thr):
    P = (probs >= thr).astype(int)
    return {
        "f1_micro": float(f1_score(T, P, average="micro", zero_division=0)),
        "f1_macro": float(f1_score(T, P, average="macro", zero_division=0)),
        "p_micro": float(precision_score(T, P, average="micro", zero_division=0)),
        "r_micro": float(recall_score(T, P, average="micro", zero_division=0)),
    }


def _map(T, probs, n_total, n_reach):
    """MAP por documento: (reachable, strict)."""
    reach, strict = [], []
    for r in range(len(T)):
        if n_total[r] == 0:
            continue
        ap = float(average_precision_score(T[r], probs[r])) if n_reach[r] > 0 else 0.0
        if n_reach[r] > 0:
            reach.append(ap)
        strict.append(ap * (n_reach[r] / n_total[r]))
    return (float(np.mean(reach)) if reach else 0.0, float(np.mean(strict)) if strict else 0.0)


def _train_freq(train_path, code_to_idx, full_codes):
    """Frecuencia de cada código del vocabulario en el corpus de entrenamiento."""
    freq = np.zeros(len(code_to_idx), dtype=np.int32)
    if not Path(train_path).exists():
        return freq
    df = pd.read_csv(train_path)
    df.columns = df.columns.str.strip()
    for s_labels in df.dropna(subset=["labels"])["labels"]:
        for c in parse_labels(s_labels, full=full_codes):
            i = code_to_idx.get(c)
            if i is not None:
                freq[i] += 1
    return freq


def _freq_buckets(T, probs, thr, freq):
    """F1 sobre test agrupando los códigos por su frecuencia en entrenamiento."""
    P = (probs >= thr).astype(int)
    spec = [("1", 1, 1), ("2-5", 2, 5), ("6-20", 6, 20), (">20", 21, 10**9)]
    out = {}
    for name, lo, hi in spec:
        cols = np.where((freq >= lo) & (freq <= hi))[0]
        if cols.size == 0:
            continue
        Tc, Pc = T[:, cols], P[:, cols]
        out[name] = {
            "n_codigos": int(cols.size),
            "support": int(Tc.sum()),
            "f1_micro": float(f1_score(Tc, Pc, average="micro", zero_division=0)),
            "f1_macro": float(f1_score(Tc, Pc, average="macro", zero_division=0)),
            "r_micro": float(recall_score(Tc, Pc, average="micro", zero_division=0)),
        }
    return out


def _block_level(gold_lists, probs, idx_to_code, thr):
    """Metricas a bloque de 3 caracteres, comparables con baseline_dict.py."""
    blocks = sorted({c[:3] for c in idx_to_code.values() if c})
    b_to_j = {b: j for j, b in enumerate(blocks)}
    cols = [[] for _ in blocks]
    for i in range(probs.shape[1]):
        code = idx_to_code.get(str(i), "")
        if code:
            cols[b_to_j[code[:3]]].append(i)
    B = np.stack([probs[:, np.asarray(c)].max(axis=1) for c in cols], axis=1)

    G = np.zeros((len(gold_lists), len(blocks)), dtype=np.int8)
    n_total = np.zeros(len(gold_lists), dtype=np.int32)
    n_reach = np.zeros(len(gold_lists), dtype=np.int32)
    for r, codes in enumerate(gold_lists):
        for b in dict.fromkeys(c[:3] for c in codes):
            n_total[r] += 1
            j = b_to_j.get(b)
            if j is not None:
                G[r, j] = 1
                n_reach[r] += 1
    Pb = (B >= thr).astype(int)
    m_reach, m_strict = _map(G, B, n_total, n_reach)
    return {
        "n_bloques_vocabulario": len(blocks),
        "threshold": thr,
        "f1_micro": float(f1_score(G, Pb, average="micro", zero_division=0)),
        "f1_macro": float(f1_score(G, Pb, average="macro", zero_division=0)),
        "p_micro": float(precision_score(G, Pb, average="micro", zero_division=0)),
        "r_micro": float(recall_score(G, Pb, average="micro", zero_division=0)),
        "map_reachable": m_reach,
        "map_strict": m_strict,
        "gold_pairs_total": int(n_total.sum()),
        "gold_pairs_reachable": int(n_reach.sum()),
    }


def _load(path, code_to_idx, num_codes, full_codes):
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=["text", "labels"]).reset_index(drop=True)
    texts = df["text"].astype(str).tolist()
    gold = [parse_labels(s, full=full_codes) for s in df["labels"]]
    T, n_total, n_reach, unseen = _build_gold(gold, code_to_idx, num_codes)
    return texts, T, n_total, n_reach, unseen, gold


def main():
    ap = argparse.ArgumentParser(
        description="Evalúa el clasificador CIE-10 sobre test (+ barrido de umbral en val)."
    )
    ap.add_argument("--model_dir", default=str(Path(__file__).parent / "model"))
    ap.add_argument("--test_file", default="/data/codiesp_csvs/codiesp_D_source_test.csv")
    ap.add_argument("--val_file", default="/data/codiesp_csvs/codiesp_D_source_validation.csv")
    ap.add_argument(
        "--no_sweep", action="store_true", help="No barrer umbral en val; usar solo --threshold."
    )
    ap.add_argument("--device", default="auto", help="cuda | cpu | auto (autodetecta).")
    ap.add_argument("--threshold", type=float, default=0.3, help="Umbral global de referencia.")
    ap.add_argument("--batch_size", type=int, default=8)
    ap.add_argument("--out", default=None)
    # Evaluar un checkpoint concreto sin tocar config.json: comparar candidatos exige medirlos
    # uno tras otro, y reescribir el fichero entre medias deja el servicio apuntando a otro.
    ap.add_argument("--model_file", default=None, help="Checkpoint a evaluar.")
    ap.add_argument("--thresholds_file", default=None, help="Umbrales por clase del checkpoint.")
    args = ap.parse_args()

    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    overrides = {
        k: v
        for k, v in (
            ("model_file", args.model_file),
            ("thresholds_file", args.thresholds_file),
        )
        if v
    }
    clf = CIE10Classifier(args.model_dir, device=device, overrides=overrides or None)
    code_to_idx = clf.code_to_idx
    num_codes = len(code_to_idx)
    full_codes = bool(clf.config.get("full_codes", True))
    max_length = int(clf.config.get("max_length", 512))
    print(
        f"[eval] modelo={clf.config.get('model_file')}  códigos={num_codes}  "
        f"full_codes={full_codes}  max_length={max_length}  device={device}"
    )

    print("[eval] inferencia sobre TEST…")
    texts_te, T_te, ntot_te, nreach_te, unseen_te, gold_te = _load(
        args.test_file, code_to_idx, num_codes, full_codes
    )
    probs_te = _infer(clf, texts_te, max_length, args.batch_size)
    tot, reach = int(ntot_te.sum()), int(nreach_te.sum())
    print(
        f"[eval] test: {len(texts_te)} docs; gold {tot} pares, alcanzables {reach} "
        f"({100 * reach / max(1, tot):.1f}%); códigos fuera de vocab={len(unseen_te)}"
    )

    have_val = (not args.no_sweep) and Path(args.val_file).exists()
    probs_va = T_va = None
    if have_val:
        print("[eval] inferencia sobre VALIDACIÓN (para barrido de umbral)…")
        texts_va, T_va, ntot_va, nreach_va, _, _ = _load(
            args.val_file, code_to_idx, num_codes, full_codes
        )
        probs_va = _infer(clf, texts_va, max_length, args.batch_size)

    grid = [round(x, 2) for x in np.arange(0.05, 0.61, 0.05)]
    sweep = []
    for t in grid:
        row = {"threshold": t, "test": _f1(T_te, probs_te, t)}
        if have_val:
            row["val"] = _f1(T_va, probs_va, t)
        sweep.append(row)

    if have_val:
        best = max(sweep, key=lambda r: r["val"]["f1_micro"])
        best_t = best["threshold"]
    else:
        best_t = args.threshold

    map_reach, map_strict = _map(T_te, probs_te, ntot_te, nreach_te)

    per_class = None
    thr_file = clf.config.get("thresholds_file")
    if thr_file and (Path(args.model_dir) / thr_file).exists():
        with open(Path(args.model_dir) / thr_file, encoding="utf-8") as f:
            pct = json.load(f).get("per_class_thresholds")
        if pct and len(pct) == num_codes:
            per_class = np.asarray(pct, dtype=np.float32)
            P_pc = (probs_te >= per_class[None, :]).astype(int)
            pc = per_class
            per_class = {
                "f1_micro": float(f1_score(T_te, P_pc, average="micro", zero_division=0)),
                "f1_macro": float(f1_score(T_te, P_pc, average="macro", zero_division=0)),
            }
            if have_val:
                P_va = (probs_va >= pc[None, :]).astype(int)
                per_class["val_f1_micro"] = float(
                    f1_score(T_va, P_va, average="micro", zero_division=0)
                )

    print("\n================ BARRIDO DE UMBRAL GLOBAL ================")
    hdr = "  umbral   F1-mi(val)  F1-ma(val)  F1-mi(test)  F1-ma(test)"
    print(hdr if have_val else "  umbral   F1-mi(test)  F1-ma(test)")
    for r in sweep:
        mark = " <= mejor en val" if r["threshold"] == best_t else ""
        if have_val:
            print(
                f"   {r['threshold']:.2f}     {r['val']['f1_micro']:.4f}      "
                f"{r['val']['f1_macro']:.4f}      {r['test']['f1_micro']:.4f}       "
                f"{r['test']['f1_macro']:.4f}{mark}"
            )
        else:
            print(
                f"   {r['threshold']:.2f}     {r['test']['f1_micro']:.4f}       {r['test']['f1_macro']:.4f}{mark}"
            )

    print("\n================ RESUMEN SOBRE TEST ================")
    te_best = next(r["test"] for r in sweep if r["threshold"] == best_t)
    print(f"  Umbral óptimo en val: {best_t}")
    print(
        f"    → TEST  F1-micro={te_best['f1_micro']:.4f}  F1-macro={te_best['f1_macro']:.4f}  "
        f"P={te_best['p_micro']:.4f}  R={te_best['r_micro']:.4f}"
    )
    if per_class:
        print(
            f"  Umbrales por clase (ablación): TEST F1-micro={per_class['f1_micro']:.4f}  "
            f"F1-macro={per_class['f1_macro']:.4f}"
        )
    print(f"  MAP por documento (reachable): {map_reach:.4f}   <- comparable al MAP de validación")
    print(f"  MAP por documento (estricto):  {map_strict:.4f}   <- comparable al benchmark CodiEsp")
    print("====================================================")

    def _toklens(_txts):
        return [len(clf.tokenizer(t, truncation=False)["input_ids"]) for t in _txts]

    _sets = {
        "train": "/data/codiesp_csvs/codiesp_D_source_train.csv",
        "val": args.val_file,
        "test": args.test_file,
    }
    token_lengths = {}
    print("\n=== Longitud en tokens por conjunto (tokenizador del modelo) ===")
    print(
        f"  {'conjunto':8s} {'n':>4s} {'media':>6s} {'mediana':>7s} {'>512':>6s} {'max':>6s} {'<2048':>7s}"
    )
    for _name, _path in _sets.items():
        if not Path(_path).exists():
            continue
        _txts = pd.read_csv(_path)["text"].dropna().astype(str).tolist()
        _tl = _toklens(_txts)
        token_lengths[_name] = _tl
        _a = np.array(_tl)
        print(
            f"  {_name:8s} {len(_a):4d} {_a.mean():6.0f} {np.median(_a):7.0f} "
            f"{100 * (_a > 512).mean():5.1f}% {int(_a.max()):6d} {100 * (_a < 2048).mean():6.1f}%"
        )
    P_glob_te = (probs_te >= args.threshold).astype(int)
    chap_cols = {}
    for i in range(num_codes):
        code = clf.idx_to_code.get(str(i), "")
        ch = _extract_chapter(code)
        if ch:
            chap_cols.setdefault(ch, []).append(i)
    per_chapter = {}
    for ch, cols in chap_cols.items():
        idx = np.asarray(cols)
        Tc, Pc = T_te[:, idx], P_glob_te[:, idx]
        if int(Tc.sum()) == 0:
            continue
        per_chapter[ch] = {
            "f1_micro": float(f1_score(Tc, Pc, average="micro", zero_division=0)),
            "support": int(Tc.sum()),
        }
    train_path = _sets["train"]
    freq = _train_freq(train_path, code_to_idx, full_codes)
    per_freq = _freq_buckets(T_te, probs_te, args.threshold, freq)
    block = _block_level(gold_te, probs_te, clf.idx_to_code, args.threshold)

    print("\n=== F1 sobre TEST por frecuencia del codigo en ENTRENAMIENTO ===")
    print(
        f"  {'frec.':>6s} {'codigos':>8s} {'support':>8s} {'F1-mi':>7s} {'F1-ma':>7s} {'R-mi':>7s}"
    )
    for k, v in per_freq.items():
        print(
            f"  {k:>6s} {v['n_codigos']:8d} {v['support']:8d} "
            f"{v['f1_micro']:7.4f} {v['f1_macro']:7.4f} {v['r_micro']:7.4f}"
        )

    print("\n=== NIVEL DE BLOQUE (3 caracteres): comparable con baseline_dict.py ===")
    print(
        f"  F1-micro={block['f1_micro']:.4f}  F1-macro={block['f1_macro']:.4f}  "
        f"P={block['p_micro']:.4f}  R={block['r_micro']:.4f}"
    )
    print(f"  MAP estricto={block['map_strict']:.4f}  MAP reachable={block['map_reachable']:.4f}")

    out = args.out or str(Path(args.model_dir) / "eval_test.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(
            {
                "best_threshold_val": best_t,
                "test_at_best": te_best,
                "per_class_test": per_class,
                "map_reachable": map_reach,
                "map_strict": map_strict,
                "sweep": sweep,
                "n_docs_test": len(texts_te),
                "gold_pairs_total": tot,
                "gold_pairs_reachable": reach,
                "unseen_unique_codes": len(unseen_te),
                "token_lengths": token_lengths,
                "per_chapter": per_chapter,
                "per_train_freq": per_freq,
                "block_level": block,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"[eval] resultados guardados en {out}")


if __name__ == "__main__":
    main()
