"""Reordenación post-hoc de las salidas del modelo para mejorar el MAP por documento.

El MAP mide el ranking de los 1767 códigos DENTRO de cada documento, pero el modelo se
entrena con un `pos_weight` distinto por clase, que desplaza el logit de cada código en
distinta magnitud. El efecto es que los códigos frecuentes aparecen arriba en TODOS los
documentos, aunque el modelo no tenga evidencia particular para este. Intentar corregirlo
durante el entrenamiento (pos_weight_cap=3) resultó contraproducente; aquí se corrige
después, sobre los logits ya calculados: no toca el modelo ni el coste de inferencia.

Dos transformaciones, ambas con sus hiperparámetros ajustados SOLO en validación y
aplicadas sin retocar sobre el conjunto de prueba:

  1. Calibración entre clases:  s_c = (z_c − λ·μ_c) / σ_c^γ
     μ_c y σ_c son media y desviación del logit de la clase c sobre un corpus de
     referencia. Son estadísticos de la SALIDA del modelo: no usan las etiquetas, de
     modo que en producción se calcularían sobre informes sin anotar. Por defecto se
     usa validación y no entrenamiento: el modelo ha memorizado el corpus de
     entrenamiento (probabilidad media del 97 % en los positivos), así que sus logits
     ahí no describen el comportamiento que tendrá ante un informe nuevo.
     (λ=0, γ=0) reproduce exactamente el ranking original.

  2. Fusión con el baseline de diccionario: bonificación β·confianza a los logits de todos
     los códigos cuyo bloque (los 3 primeros caracteres) hizo match por regex en el texto.
     El diccionario corre sobre CPU, así que su coste en el VPS es despreciable.

Las probabilidades se cachean en --cache_dir: repetir barridos no reejecuta el encoder.

Uso (imagen cie-10-training):
  python3 rerank_map.py --ckpt /app/model/classifier.pt --label prod
  python3 rerank_map.py --ckpt /app/model/classifier_soup.pt --label soup --dict_patterns /app/model/baseline_dict.json
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, f1_score

SPLITS = ("train", "val", "test")


# --------------------------------------------------------------------------
# Datos e inferencia (con caché en disco)
# --------------------------------------------------------------------------
# torch y train se importan dentro de las funciones que los necesitan: así las
# transformaciones y las métricas (numpy puro) se pueden probar sin cargar el modelo.
def load_split(path):
    from train import parse_labels

    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=["text", "labels"]).reset_index(drop=True)
    return df["text"].astype(str).tolist(), [parse_labels(s, full=True) for s in df["labels"]]


def probs_for(split, texts, args, cache_dir):
    """Probabilidades (n_docs, n_codes); se reutiliza la caché si ya existen."""
    cache = cache_dir / f"{args.label}_{split}.npy"
    c2i_cache = cache_dir / f"{args.label}_code_to_idx.json"
    if cache.exists() and c2i_cache.exists():
        print(f"[cache] {cache.name}", flush=True)
        with open(c2i_cache) as f:
            return np.load(cache), json.load(f)

    import torch

    from ensemble_eval import infer

    print(f"[infer] {split} ({len(texts)} docs) con {args.ckpt}", flush=True)
    p, c2i = infer(
        args.ckpt,
        texts,
        args.model_name,
        args.max_length,
        args.batch_size,
        torch.device(args.device),
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.save(cache, p)
    with open(c2i_cache, "w") as f:
        json.dump(c2i, f)
    return p, c2i


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


# --------------------------------------------------------------------------
# MAP
# --------------------------------------------------------------------------
def _ap(scores, target):
    """AP de un documento. Equivale a average_precision_score con etiquetas binarias."""
    order = np.argsort(-scores, kind="stable")
    hits = target[order]
    npos = int(hits.sum())
    if npos == 0:
        return 0.0
    cum = np.cumsum(hits)
    prec = cum / np.arange(1, len(hits) + 1)
    return float((prec * hits).sum() / npos)


def map_scores(T, S, n_total, n_reach):
    """(MAP alcanzable, MAP estricto) sobre una matriz de puntuaciones S."""
    reach, strict = [], []
    for r in range(len(T)):
        if n_total[r] == 0:
            continue
        ap = _ap(S[r], T[r]) if n_reach[r] > 0 else 0.0
        if n_reach[r] > 0:
            reach.append(ap)
        strict.append(ap * (n_reach[r] / n_total[r]))
    return float(np.mean(reach)), float(np.mean(strict))


def map_strict_sklearn(T, S, n_total, n_reach):
    """Misma métrica con sklearn: control de que el AP rápido no cambia el número."""
    strict = []
    for r in range(len(T)):
        if n_total[r] == 0:
            continue
        ap = float(average_precision_score(T[r], S[r])) if n_reach[r] > 0 else 0.0
        strict.append(ap * (n_reach[r] / n_total[r]))
    return float(np.mean(strict))


# --------------------------------------------------------------------------
# Transformaciones
# --------------------------------------------------------------------------
def to_logits(p, eps=1e-12):
    p = np.clip(p.astype(np.float64), eps, 1 - eps)
    return np.log(p / (1 - p))


def calibrate(Z, mu, sigma, lam, gamma):
    """s_c = (z_c − λ·μ_c) / σ_c^γ. Con λ=γ=0 devuelve Z sin tocar."""
    S = Z - lam * mu
    if gamma:
        S = S / np.power(np.maximum(sigma, 1e-6), gamma)
    return S


def dict_bonus_matrix(texts, patterns_path, idx_to_code, cache_path):
    """Matriz (n_docs, n_codes) con la confianza del diccionario para el bloque de cada código."""
    if cache_path.exists():
        print(f"[cache] {cache_path.name}", flush=True)
        return np.load(cache_path)

    from baseline_dict import DictClassifier

    clf = DictClassifier(patterns_path)
    blocks = np.array([c.upper()[:3] for c in idx_to_code])
    block_cols = {b: np.where(blocks == b)[0] for b in set(blocks.tolist())}
    B = np.zeros((len(texts), len(idx_to_code)), dtype=np.float32)
    for r, text in enumerate(texts):
        for hit in clf.predict(text):
            cols = block_cols.get(hit["code"].upper()[:3])
            if cols is not None and len(cols):
                B[r, cols] = max(float(hit["confidence"]), 0.0)
        if (r + 1) % 25 == 0:
            print(f"  diccionario {r + 1}/{len(texts)}", end="\r", flush=True)
    print()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache_path, B)
    return B


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="/app/model/classifier.pt")
    ap.add_argument("--label", default="prod", help="Nombre corto: da nombre a la caché")
    ap.add_argument("--model_name", default="IIC/RigoBERTa-Clinical")
    ap.add_argument("--max_length", type=int, default=512)
    ap.add_argument("--batch_size", type=int, default=8)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--train_file", default="/data/codiesp_csvs/codiesp_D_source_train.csv")
    ap.add_argument("--val_file", default="/data/codiesp_csvs/codiesp_D_source_validation.csv")
    ap.add_argument("--test_file", default="/data/codiesp_csvs/codiesp_D_source_test.csv")
    ap.add_argument(
        "--dict_patterns", default="", help="baseline_dict.json; vacío desactiva la fusión"
    )
    ap.add_argument(
        "--stats_split",
        default="val",
        choices=["val", "train", "both"],
        help="Corpus sobre el que se calculan mu_c y sigma_c (sin usar sus etiquetas)",
    )
    ap.add_argument("--cache_dir", default="/app/model/logits_cache")
    ap.add_argument("--out", default="/app/model/rerank_map.json")
    args = ap.parse_args()
    cache_dir = Path(args.cache_dir)

    files = {"train": args.train_file, "val": args.val_file, "test": args.test_file}
    texts, gold, probs = {}, {}, {}
    c2i = None
    for s in SPLITS:
        texts[s], gold[s] = load_split(files[s])
        probs[s], c2i = probs_for(s, texts[s], args, cache_dir)
    idx_to_code = [None] * len(c2i)
    for code, i in c2i.items():
        idx_to_code[i] = code

    T, n_total, n_reach = {}, {}, {}
    for s in ("val", "test"):
        T[s], n_total[s], n_reach[s] = build_gold(gold[s], c2i, len(c2i))
        print(
            f"[data] {s}: {len(texts[s])} docs, {int(n_total[s].sum())} códigos gold "
            f"({int(n_reach[s].sum())} en vocabulario)",
            flush=True,
        )

    Z = {s: to_logits(probs[s]) for s in SPLITS}
    ref = np.vstack([Z["train"], Z["val"]]) if args.stats_split == "both" else Z[args.stats_split]
    mu = ref.mean(axis=0)
    sigma = ref.std(axis=0)
    print(
        f"[calib] estadísticos por clase sobre '{args.stats_split}' ({len(ref)} docs)", flush=True
    )

    # Referencia: ranking original
    base = {}
    for s in ("val", "test"):
        mr, ms = map_scores(T[s], Z[s], n_total[s], n_reach[s])
        base[s] = {"map_reachable": mr, "map_strict": ms}
    chk = map_strict_sklearn(T["test"], Z["test"], n_total["test"], n_reach["test"])
    print(
        f"\n[control] MAP strict test = {base['test']['map_strict']:.4f} "
        f"(sklearn: {chk:.4f}, diferencia {abs(chk - base['test']['map_strict']):.5f})",
        flush=True,
    )

    # Matrices del diccionario (opcional)
    B = None
    if args.dict_patterns:
        # El diccionario depende de spaCy (lematización). Si no está en la imagen, se
        # continúa sin fusión en vez de tirar el run después de toda la inferencia.
        try:
            B = {
                s: dict_bonus_matrix(
                    texts[s], args.dict_patterns, idx_to_code, cache_dir / f"dict_{s}.npy"
                )
                for s in ("val", "test")
            }
            cov = float((B["test"] > 0).any(axis=1).mean())
            print(f"[dict] documentos de prueba con algún bloque detectado: {cov:.1%}", flush=True)
        except Exception as exc:  # noqa: BLE001, cualquier fallo desactiva la fusión
            print(f"[dict] fusión desactivada: {type(exc).__name__}: {exc}", flush=True)
            B = None

    # Barrido conjunto sobre VALIDACIÓN
    lambdas = [0.0, 0.25, 0.5, 0.75, 1.0]
    gammas = [0.0, 0.25, 0.5, 0.75, 1.0]
    betas = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0] if B is not None else [0.0]
    grid = []
    best = None
    print("\n[sweep] MAP strict de validación", flush=True)
    for lam in lambdas:
        for gam in gammas:
            Sv = calibrate(Z["val"], mu, sigma, lam, gam)
            for beta in betas:
                Svb = Sv if beta == 0.0 else Sv + beta * B["val"]
                _, ms = map_scores(T["val"], Svb, n_total["val"], n_reach["val"])
                grid.append({"lambda": lam, "gamma": gam, "beta": beta, "map_strict_val": ms})
                if best is None or ms > best["map_strict_val"]:
                    best = grid[-1]
        print(
            f"  lambda={lam:.2f} mejor hasta ahora: {best['map_strict_val']:.4f} "
            f"(λ={best['lambda']}, γ={best['gamma']}, β={best['beta']})",
            flush=True,
        )

    # Aplicación a PRUEBA con los hiperparámetros elegidos en validación
    results = {
        "baseline": base,
        "best_val": best,
        "grid": grid,
        "label": args.label,
        "stats_split": args.stats_split,
    }
    for s in ("val", "test"):
        S = calibrate(Z[s], mu, sigma, best["lambda"], best["gamma"])
        if best["beta"]:
            S = S + best["beta"] * B[s]
        mr, ms = map_scores(T[s], S, n_total[s], n_reach[s])
        results[f"rerank_{s}"] = {"map_reachable": mr, "map_strict": ms}

    # Ablación: cada pieza por separado, con su propio mejor hiperparámetro en validación
    def best_of(keep):
        sub = [g for g in grid if keep(g)]
        return max(sub, key=lambda g: g["map_strict_val"])

    ablation = {"solo_calibracion": best_of(lambda g: g["beta"] == 0.0)}
    if B is not None:
        ablation["solo_diccionario"] = best_of(lambda g: g["lambda"] == 0.0 and g["gamma"] == 0.0)
    for cfg in ablation.values():
        S = calibrate(Z["test"], mu, sigma, cfg["lambda"], cfg["gamma"])
        if cfg["beta"]:
            S = S + cfg["beta"] * B["test"]
        mr, ms = map_scores(T["test"], S, n_total["test"], n_reach["test"])
        cfg["map_strict_test"] = ms
        cfg["map_reachable_test"] = mr
    results["ablacion"] = ablation

    # F1: el umbral ya no es comparable tras reescalar, así que se rebarre en validación
    # y se reutiliza en prueba (el ranking, no el umbral, es lo que persigue este experimento).
    Sv = calibrate(Z["val"], mu, sigma, best["lambda"], best["gamma"])
    St = calibrate(Z["test"], mu, sigma, best["lambda"], best["gamma"])
    if best["beta"]:
        Sv, St = Sv + best["beta"] * B["val"], St + best["beta"] * B["test"]
    thr_grid = np.quantile(Sv, np.linspace(0.990, 0.9995, 20))
    f1s = [
        (
            float(f1_score(T["val"], (Sv >= t).astype(int), average="micro", zero_division=0)),
            float(t),
        )
        for t in thr_grid
    ]
    f1_val, thr = max(f1s)
    f1_test = float(f1_score(T["test"], (St >= thr).astype(int), average="micro", zero_division=0))
    results["f1"] = {"thr": thr, "f1_micro_val": f1_val, "f1_micro_test": f1_test}

    print("\n===== RESULTADOS =====")
    print(f"{'variante':24} {'MAPstrict val':>14} {'MAPstrict test':>15}")
    print(f"{'original':24} {base['val']['map_strict']:14.4f} {base['test']['map_strict']:15.4f}")
    for name, cfg in ablation.items():
        print(f"{name:24} {cfg['map_strict_val']:14.4f} {cfg['map_strict_test']:15.4f}")
    print(
        f"{'calibración+diccionario':24} {results['rerank_val']['map_strict']:14.4f} "
        f"{results['rerank_test']['map_strict']:15.4f}"
    )
    print(f"\nmejor en validación: λ={best['lambda']} γ={best['gamma']} β={best['beta']}")
    print(f"F1-micro: val={f1_val:.4f} test={f1_test:.4f} (umbral {thr:.3f})")
    delta = results["rerank_test"]["map_strict"] - base["test"]["map_strict"]
    print(f"Δ MAP strict test = {delta:+.4f} ({delta * 100:+.2f} pp)")

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[save] {args.out}")


if __name__ == "__main__":
    main()
