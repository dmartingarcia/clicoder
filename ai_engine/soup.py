"""Sopa de pesos: promedia los PESOS de varios checkpoints en un único modelo.

El promediado de probabilidades (ensemble_eval.py) mejora el MAP pero multiplica el
coste de inferencia por el número de modelos, lo que lo hace inviable en el VPS sin GPU.
La sopa de pesos busca la misma ganancia a coste cero: produce UN solo modelo, con el
mismo tamaño y la misma latencia que el actual.

Tiene sentido aquí porque todas las ejecuciones parten del mismo checkpoint preentrenado
(RigoBERTa-Clinical) y solo divergen en la semilla y en el orden de los lotes: los mínimos
que alcanzan quedan conectados dentro de la misma cuenca de la función de pérdida, de modo
que el promedio de sus pesos sigue siendo un punto válido (Wortsman et al., 2022).

Dos variantes:
  uniforme — promedia todos los checkpoints dados.
  voraz    — ordena por MAP de validación y añade uno a uno, conservando el candidato
             solo si el MAP de VALIDACIÓN mejora. El conjunto de prueba nunca interviene.

Uso (imagen cie-10-training):
  python3 soup.py --ckpts a.pt b.pt c.pt --labels 37ctrl 37a 37b --greedy
"""

import argparse
import json

import numpy as np
import pandas as pd
import torch
from transformers import AutoTokenizer

from ensemble_eval import best_f1, build_gold, maps, metrics_at
from train import FlatClassifier, _autocast_ctx, parse_labels

_TOK = None


def _tokenizer(model_name):
    global _TOK
    if _TOK is None:
        _TOK = AutoTokenizer.from_pretrained(model_name)
    return _TOK


def load_ckpt(path):
    return torch.load(path, map_location="cpu", weights_only=False)


def average_states(paths):
    """Media de los model_state_dict de `paths`, leyéndolos de uno en uno.

    Los tensores no reales (buffers enteros como position_ids) no se promedian:
    se toman del primer checkpoint.
    """
    acc, dtypes, ref_c2i = None, None, None
    for path in paths:
        ck = load_ckpt(path)
        sd = ck["model_state_dict"]
        if ref_c2i is None:
            ref_c2i = ck["code_to_idx"]
        elif ck["code_to_idx"] != ref_c2i:
            raise ValueError(f"{path}: vocabulario de códigos distinto, no se puede promediar")
        if acc is None:
            dtypes = {k: v.dtype for k, v in sd.items()}
            acc = {
                k: (v.double().clone() if v.is_floating_point() else v.clone())
                for k, v in sd.items()
            }
        else:
            if acc.keys() != sd.keys():
                raise ValueError(f"{path}: las claves del state_dict no coinciden")
            for k, v in sd.items():
                if v.is_floating_point():
                    acc[k] += v.double()
        del ck, sd
    n = len(paths)
    return {
        k: ((v / n).to(dtypes[k]) if v.is_floating_point() else v) for k, v in acc.items()
    }, ref_c2i


def infer_state(state, code_to_idx, texts, model_name, max_length, batch_size, device):
    model = FlatClassifier(model_name, len(code_to_idx), dropout=0.0, freeze_layers=0)
    model.load_state_dict(state)
    model.to(device).eval()
    tok = _tokenizer(model_name)
    probs = np.zeros((len(texts), len(code_to_idx)), dtype=np.float32)
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
    return probs


def load_split(path, full=True):
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=["text", "labels"]).reset_index(drop=True)
    return df["text"].astype(str).tolist(), [parse_labels(s, full=full) for s in df["labels"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpts", nargs="+", required=True)
    ap.add_argument("--labels", nargs="+", required=True, help="Etiqueta corta por checkpoint")
    ap.add_argument(
        "--greedy", action="store_true", help="Sopa voraz guiada por el MAP de validación"
    )
    ap.add_argument("--model_name", default="IIC/RigoBERTa-Clinical")
    ap.add_argument("--max_length", type=int, default=512)
    ap.add_argument("--batch_size", type=int, default=8)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--val_file", default="/data/codiesp_csvs/codiesp_D_source_validation.csv")
    ap.add_argument("--test_file", default="/data/codiesp_csvs/codiesp_D_source_test.csv")
    ap.add_argument("--save", default="/app/model/classifier_soup.pt")
    ap.add_argument("--save_probs_dir", default="/app/model/logits_cache")
    ap.add_argument("--out", default="/app/model/soup_eval.json")
    args = ap.parse_args()
    device = torch.device(args.device)

    val_texts, val_gold = load_split(args.val_file)
    test_texts, test_gold = load_split(args.test_file)
    print(f"[data] val={len(val_texts)} test={len(test_texts)}", flush=True)

    _, c2i = average_states(args.ckpts[:1])  # valida formato y recupera el vocabulario
    Tv, nv_total, nv_reach = build_gold(val_gold, c2i, len(c2i))
    Tt, nt_total, nt_reach = build_gold(test_gold, c2i, len(c2i))

    def val_map(state):
        p = infer_state(
            state, c2i, val_texts, args.model_name, args.max_length, args.batch_size, device
        )
        return maps(Tv, p, nv_total, nv_reach)[1], p

    results = {}

    # 1) MAP individual de cada checkpoint en validación — ordena la sopa voraz
    singles = {}
    for path, lab in zip(args.ckpts, args.labels, strict=True):
        print(f"[val] {lab}", flush=True)
        ms, _ = val_map(load_ckpt(path)["model_state_dict"])
        singles[lab] = {"path": path, "map_strict_val": ms}
        print(f"      MAP strict val = {ms:.4f}", flush=True)
    results["individuales_val"] = {k: v["map_strict_val"] for k, v in singles.items()}

    # 2) Sopa uniforme
    print("\n[soup] uniforme sobre todos los checkpoints", flush=True)
    state, _ = average_states(args.ckpts)
    uni_map, _ = val_map(state)
    print(f"      MAP strict val = {uni_map:.4f}", flush=True)
    results["uniforme_val"] = uni_map
    best_state, best_map, best_set = state, uni_map, list(args.labels)

    # 3) Sopa voraz: se añade un candidato solo si el MAP de VALIDACIÓN mejora
    if args.greedy:
        order = sorted(args.labels, key=lambda lb: -singles[lb]["map_strict_val"])
        chosen = [order[0]]
        cur_map = singles[order[0]]["map_strict_val"]
        print(f"\n[greedy] semilla: {order[0]} (MAP val {cur_map:.4f})", flush=True)
        for lab in order[1:]:
            cand = chosen + [lab]
            st, _ = average_states([singles[c]["path"] for c in cand])
            m, _ = val_map(st)
            keep = m > cur_map
            print(
                f"[greedy] +{lab:8} MAP val {m:.4f}  {'ACEPTADO' if keep else 'descartado'}",
                flush=True,
            )
            if keep:
                chosen, cur_map = cand, m
        results["voraz_val"] = {"modelos": chosen, "map_strict_val": cur_map}
        if cur_map > best_map:
            best_state, best_map, best_set = (
                average_states([singles[c]["path"] for c in chosen])[0],
                cur_map,
                chosen,
            )

    # 4) Evaluación final de la mejor sopa en validación y prueba.
    #    El umbral de F1 se elige en validación y se REUTILIZA en prueba.
    print(f"\n[final] sopa = {best_set}  (MAP strict val {best_map:.4f})", flush=True)
    pv = infer_state(
        best_state, c2i, val_texts, args.model_name, args.max_length, args.batch_size, device
    )
    pt = infer_state(
        best_state, c2i, test_texts, args.model_name, args.max_length, args.batch_size, device
    )
    _, thr = best_f1(Tv, pv)
    for split, T, p, nt, nr in (
        ("val", Tv, pv, nv_total, nv_reach),
        ("test", Tt, pt, nt_total, nt_reach),
    ):
        mr, ms = maps(T, p, nt, nr)
        pr, rc, f1, f1ma = metrics_at(T, p, thr)
        results[f"sopa_{split}"] = {
            "map_reachable": mr,
            "map_strict": ms,
            "precision_micro": pr,
            "recall_micro": rc,
            "f1_micro": f1,
            "f1_macro": f1ma,
            "thr": thr,
        }
        print(
            f"{split:5} MAPstrict={ms:.4f} MAPreach={mr:.4f} "
            f"P={pr:.4f} R={rc:.4f} F1mi={f1:.4f} F1ma={f1ma:.4f} thr={thr:.2f}",
            flush=True,
        )

    results["sopa_modelos"] = best_set
    if args.save:
        ck0 = load_ckpt(singles[best_set[0]]["path"])
        torch.save(
            {"code_to_idx": c2i, "idx_to_code": ck0["idx_to_code"], "model_state_dict": best_state},
            args.save,
        )
        print(f"[save] {args.save}")
    if args.save_probs_dir:
        from pathlib import Path

        d = Path(args.save_probs_dir)
        d.mkdir(parents=True, exist_ok=True)
        np.save(d / "soup_val.npy", pv)
        np.save(d / "soup_test.npy", pt)
        # Mismo formato de caché que rerank_map.py, para encadenar sin reejecutar el encoder
        with open(d / "soup_code_to_idx.json", "w") as f:
            json.dump(c2i, f)
        print(f"[save] probabilidades en {d}")
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[save] {args.out}")


if __name__ == "__main__":
    main()
