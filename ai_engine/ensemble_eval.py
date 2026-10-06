"""Evalúa checkpoints sueltos y su ensemble (media de probabilidades) sobre val y test.

MAP por documento estilo CodiEsp en dos variantes (igual que eval_test.py):
  reachable: solo el gold que el modelo puede predecir
  strict   : gold completo; los códigos fuera del vocabulario penalizan
"""

import argparse
import json

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
)
from transformers import AutoTokenizer

from train import FlatClassifier, _autocast_ctx, parse_labels


def infer(ckpt_path, texts, model_name, max_length, batch_size, device):
    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    code_to_idx = ck["code_to_idx"]
    model = FlatClassifier(model_name, len(code_to_idx), dropout=0.0, freeze_layers=0)
    model.load_state_dict(ck["model_state_dict"])
    model.to(device).eval()
    tok = AutoTokenizer.from_pretrained(model_name)
    probs = np.zeros((len(texts), len(code_to_idx)), dtype=np.float32)
    # FlashAttention solo admite fp16/bf16: mismo autocast que usa evaluate() en train.py
    with torch.no_grad(), _autocast_ctx(device):
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
    del model
    torch.cuda.empty_cache()
    return probs, code_to_idx


def build_gold(gold_lists, code_to_idx, num_codes):
    T = np.zeros((len(gold_lists), num_codes), dtype=np.int8)
    n_total = np.zeros(len(gold_lists), dtype=np.int32)
    n_reach = np.zeros(len(gold_lists), dtype=np.int32)
    for r, codes in enumerate(gold_lists):
        for c in dict.fromkeys(codes):
            n_total[r] += 1
            idx = code_to_idx.get(c)
            if idx is not None:
                T[r, idx] = 1
                n_reach[r] += 1
    return T, n_total, n_reach


def maps(T, probs, n_total, n_reach):
    reach, strict = [], []
    for r in range(len(T)):
        if n_total[r] == 0:
            continue
        ap = float(average_precision_score(T[r], probs[r])) if n_reach[r] > 0 else 0.0
        if n_reach[r] > 0:
            reach.append(ap)
        strict.append(ap * (n_reach[r] / n_total[r]))
    return float(np.mean(reach)), float(np.mean(strict))


def metrics_at(T, probs, thr):
    """Precision/recall/F1 micro a un umbral FIJO (sin barrido sobre este conjunto)."""
    Y = (probs >= thr).astype(int)
    return (
        float(precision_score(T, Y, average="micro", zero_division=0)),
        float(recall_score(T, Y, average="micro", zero_division=0)),
        float(f1_score(T, Y, average="micro", zero_division=0)),
        float(f1_score(T, Y, average="macro", zero_division=0)),
    )


def best_f1(T, probs):
    best = (0.0, 0.0)
    for thr in np.linspace(0.05, 0.6, 12):
        f = float(f1_score(T, (probs >= thr).astype(int), average="micro", zero_division=0))
        if f > best[0]:
            best = (f, float(thr))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpts", nargs="+", required=True)
    ap.add_argument("--labels", nargs="+", required=True, help="Etiqueta corta por checkpoint")
    ap.add_argument("--model_name", default="IIC/RigoBERTa-Clinical")
    ap.add_argument("--max_length", type=int, default=512)
    ap.add_argument("--batch_size", type=int, default=8)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out", default="/app/model/ensemble_eval.json")
    args = ap.parse_args()
    device = torch.device(args.device)  # _autocast_ctx espera torch.device, no str

    splits = {
        "val": "/data/codiesp_csvs/codiesp_D_source_validation.csv",
        "test": "/data/codiesp_csvs/codiesp_D_source_test.csv",
    }
    results = {}
    val_thr = {}  # umbral elegido en validación, se REUTILIZA en test
    for split, path in splits.items():
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=["text", "labels"]).reset_index(drop=True)
        texts = df["text"].astype(str).tolist()
        gold = [parse_labels(s, full=True) for s in df["labels"]]

        all_probs, c2i = [], None
        for ck, lab in zip(args.ckpts, args.labels, strict=True):
            print(f"[{split}] inferencia {lab}", flush=True)
            p, c2i = infer(ck, texts, args.model_name, args.max_length, args.batch_size, device)
            all_probs.append(p)

        T, n_total, n_reach = build_gold(gold, c2i, len(c2i))
        res = {}
        series = list(zip(args.labels, all_probs, strict=True))
        series.append(("ENSEMBLE", np.mean(all_probs, axis=0)))
        for lab, p in series:
            mr, ms = maps(T, p, n_total, n_reach)
            if split == "val":
                _, thr = best_f1(T, p)
                val_thr[lab] = thr
            else:
                thr = val_thr[lab]
            pr, rc, f1, f1ma = metrics_at(T, p, thr)
            res[lab] = {
                "map_reachable": mr,
                "map_strict": ms,
                "precision_micro": pr,
                "recall_micro": rc,
                "f1_micro": f1,
                "f1_macro": f1ma,
                "thr": thr,
            }
        results[split] = res

        print(f"\n===== {split.upper()} =====")
        print(
            f"{'modelo':22} {'MAPreach':>9} {'MAPstrict':>10} {'P':>7} {'R':>7} {'F1mi':>7} {'F1ma':>7} {'thr':>6}"
        )
        for lab, m in res.items():
            print(
                f"{lab:22} {m['map_reachable']:9.4f} {m['map_strict']:10.4f} "
                f"{m['precision_micro']:7.4f} {m['recall_micro']:7.4f} "
                f"{m['f1_micro']:7.4f} {m['f1_macro']:7.4f} {m['thr']:6.2f}"
            )

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[save] {args.out}")


if __name__ == "__main__":
    main()
