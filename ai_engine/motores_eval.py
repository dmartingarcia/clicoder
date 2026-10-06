#!/usr/bin/env python3
"""Compara los cuatro motores que sirve el sistema, con la misma maquinaria que el motor real.

De aquí salen las cifras titulares del modo fusionado. Existían en `model/comparativa_motores.json`
y `model/fusion_sweep.json` sin guion que las regenerase, que es justo lo que la memoria no puede
permitirse: una cifra que nadie puede reproducir.

La fusión es la que implementa `main._dict_bonus_vector`: al logit de cada código se le suma
beta por la confianza que el diccionario da a su bloque. Beta se elige por MAP estricto **en
validación** y se aplica sin retocar a prueba. No confundir con `rerank_map.py`, que además
calibra entre clases y persigue otra cosa.

Uso: python motores_eval.py [--device cuda] [--model_file X.pt] [--thresholds_file X.json]
Salidas: model/comparativa_motores.json y model/fusion_sweep.json
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import f1_score, precision_score, recall_score

from eval_test import _infer, _load, _map

BETAS = (0.0, 0.5, 1.0, 2.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 64.0)


def _bonus(dic, textos, code_to_idx) -> np.ndarray:
    """Confianza del diccionario por documento y código, sin escalar por beta.

    El diccionario predice bloques de tres caracteres, de modo que todos los códigos que cuelgan
    de un bloque reciben la misma confianza: aporta qué bloque aplica y deja el orden dentro de
    él al clasificador. Es exactamente lo que hace el motor en producción.
    """
    B = np.zeros((len(textos), len(code_to_idx)), dtype=np.float32)
    por_bloque = [{} for _ in textos]
    for fila, texto in enumerate(textos):
        for hit in dic.predict(texto):
            bloque = str(hit.get("code", "")).upper()[:3]
            conf = max(float(hit.get("confidence", 0.0)), 0.0)
            if bloque:
                por_bloque[fila][bloque] = max(por_bloque[fila].get(bloque, 0.0), conf)
        for code, idx in code_to_idx.items():
            B[fila, idx] = por_bloque[fila].get(str(code).upper()[:3], 0.0)
        print(f"  diccionario {fila + 1}/{len(textos)}", end="\r", flush=True)
    print()
    return B


def _umbral_y_f1(T_val, S_val, T_test, S_test):
    """Umbral elegido en validación por F1 y aplicado a prueba, con sus P y R."""
    rejilla = np.quantile(S_val, np.linspace(0.985, 0.9995, 40))
    mejor = max(
        (
            (float(f1_score(T_val, (S_val >= t).astype(int), average="micro", zero_division=0)), t)
            for t in rejilla
        ),
        key=lambda par: par[0],
    )
    thr = float(mejor[1])
    P = (S_test >= thr).astype(int)
    return {
        "umbral": thr,
        "f1_micro_val": mejor[0],
        "p": float(precision_score(T_test, P, average="micro", zero_division=0)),
        "r": float(recall_score(T_test, P, average="micro", zero_division=0)),
        "f1": float(f1_score(T_test, P, average="micro", zero_division=0)),
    }


def main():
    from baseline_dict import DictClassifier
    from classifier import CIE10Classifier

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model_dir", default=str(Path(__file__).parent / "model"))
    ap.add_argument("--val_file", default="/data/codiesp_csvs/codiesp_D_source_validation.csv")
    ap.add_argument("--test_file", default="/data/codiesp_csvs/codiesp_D_source_test.csv")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--model_file", default=None)
    ap.add_argument("--thresholds_file", default=None)
    ap.add_argument("--batch_size", type=int, default=8)
    args = ap.parse_args()

    overrides = {
        k: v
        for k, v in (("model_file", args.model_file), ("thresholds_file", args.thresholds_file))
        if v
    }
    clf = CIE10Classifier(args.model_dir, device=args.device, overrides=overrides or None)
    dic = DictClassifier(str(Path(args.model_dir) / "baseline_dict.json"))
    c2i, n_codes = clf.code_to_idx, len(clf.code_to_idx)
    full = bool(clf.config.get("full_codes", True))
    max_len = int(clf.config.get("max_length", 512))
    print(f"[motores] modelo={clf.version} device={args.device}")

    datos = {}
    for split, ruta in (("val", args.val_file), ("test", args.test_file)):
        print(f"[motores] {split}: inferencia…")
        textos, T, ntot, nreach, _, _ = _load(ruta, c2i, n_codes, full)
        probs = _infer(clf, textos, max_len, args.batch_size)
        Z = np.log(np.clip(probs, 1e-7, 1 - 1e-7) / np.clip(1 - probs, 1e-7, 1))
        datos[split] = {"T": T, "Z": Z, "B": _bonus(dic, textos, c2i), "nt": ntot, "nr": nreach}

    # Beta se elige en validación y se aplica sin retocar a prueba.
    rejilla = []
    for beta in BETAS:
        v = datos["val"]
        _, ms = _map(v["T"], v["Z"] + beta * v["B"], v["nt"], v["nr"])
        rejilla.append({"beta": beta, "map_strict_val": ms})
        print(f"  beta={beta:>5}  MAP val={ms:.4f}")
    beta = max(rejilla, key=lambda g: g["map_strict_val"])["beta"]
    print(f"[motores] beta elegida en validación: {beta}")

    def medir(S_val, S_test):
        v, t = datos["val"], datos["test"]
        mr, ms = _map(t["T"], S_test, t["nt"], t["nr"])
        return {
            "map_strict": ms,
            "map_reachable": mr,
            **_umbral_y_f1(v["T"], S_val, t["T"], S_test),
        }

    solo = medir(datos["val"]["Z"], datos["test"]["Z"])
    fusion = medir(
        datos["val"]["Z"] + beta * datos["val"]["B"], datos["test"]["Z"] + beta * datos["test"]["B"]
    )
    dicc = medir(datos["val"]["B"], datos["test"]["B"])

    # Modo "both": concatena lo que devuelve cada motor con su propio umbral de producción. No admite MAP:
    # dos listas de motores con escalas distintas no definen una única ordenación.
    umbral_bert = float(clf.config.get("threshold", 0.5))
    logit_bert = float(np.log(umbral_bert / (1 - umbral_bert)))
    t = datos["test"]
    P_bert = t["Z"] >= logit_bert
    P_dict = t["B"] > 0
    P_both = (P_bert | P_dict).astype(int)
    both = {
        "umbral_bert": umbral_bert,
        "p": float(precision_score(t["T"], P_both, average="micro", zero_division=0)),
        "r": float(recall_score(t["T"], P_both, average="micro", zero_division=0)),
        "f1": float(f1_score(t["T"], P_both, average="micro", zero_division=0)),
    }

    base = Path(args.model_dir)
    (base / "comparativa_motores.json").write_text(
        json.dumps(
            {
                "modelo": clf.version,
                "diccionario": dicc,
                "modelo_solo": solo,
                "modelo_fusion": fusion,
                "ambos_concatenado": both,
                "beta": beta,
            },
            indent=1,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (base / "fusion_sweep.json").write_text(
        json.dumps(
            {
                "descripcion": "Barrido de beta de la fusion modelo+diccionario. "
                "s_c = logit_c + beta*conf(bloque(c)). Elegida por MAP "
                "estricto en validacion y aplicada sin retocar a prueba.",
                "modelo": clf.version,
                "beta_grid": rejilla,
                "beta_elegido": beta,
                "diccionario_solo_map_strict_test": dicc["map_strict"],
            },
            indent=1,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"\n{'motor':<14}{'MAP':>9}{'P':>9}{'R':>9}{'F1':>9}{'umbral':>10}")
    print("-" * 60)
    for nombre, m in (("diccionario", dicc), ("clasificador", solo), ("fusionado", fusion)):
        print(
            f"{nombre:<14}{m['map_strict']:9.4f}{m['p']:9.4f}{m['r']:9.4f}"
            f"{m['f1']:9.4f}{m['umbral']:10.3f}"
        )
    print(f"{'ambos':<14}{'n/a':>9}{both['p']:9.4f}{both['r']:9.4f}{both['f1']:9.4f}{'':>10}")


if __name__ == "__main__":
    main()
