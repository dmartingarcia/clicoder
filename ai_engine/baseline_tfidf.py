"""
baseline_tfidf.py — Baseline TF-IDF + Regresión Logística para clasificación CIE-10.

Entrena un clasificador binario por código (binary relevance) usando TF-IDF sobre
el texto. Sirve como línea base para comparar con el modelo transformer.

Uso:
    python baseline_tfidf.py
    python baseline_tfidf.py --train_file ... --val_file ...
"""

import argparse
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MultiLabelBinarizer


def parse_labels(label_str: str):
    if pd.isna(label_str) or not str(label_str).strip():
        return []
    return [c.strip().upper()[:3] for c in str(label_str).split(";") if c.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train_file",
        default="/data/codiesp_csvs/codiesp_D_source_train.csv")
    parser.add_argument("--val_file",
        default="/data/codiesp_csvs/codiesp_D_source_validation.csv")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    print("[data] Cargando datos...")
    train_df = pd.read_csv(args.train_file)
    val_df   = pd.read_csv(args.val_file)
    for df in (train_df, val_df):
        df.columns = df.columns.str.strip()
        df.dropna(subset=["text", "labels"], inplace=True)
    print(f"[data] train={len(train_df)}  val={len(val_df)}")

    train_labels = [parse_labels(lbl) for lbl in train_df["labels"]]
    val_labels   = [parse_labels(lbl) for lbl in val_df["labels"]]

    mlb = MultiLabelBinarizer()
    Y_train = mlb.fit_transform(train_labels)
    Y_val   = mlb.transform(val_labels)
    print(f"[data] {len(mlb.classes_)} códigos únicos en train")

    print("\n[model] Entrenando TF-IDF + Logistic Regression (binary relevance)...")
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            min_df=2,
            max_features=50_000,
            sublinear_tf=True,
        )),
        ("clf", OneVsRestClassifier(
            LogisticRegression(C=1.0, max_iter=10000, solver="saga"),
            n_jobs=-1,
        )),
    ])
    pipeline.fit(train_df["text"].tolist(), Y_train)

    print(f"[eval] Evaluando en validación (threshold={args.threshold})...")
    Y_prob = pipeline.predict_proba(val_df["text"].tolist())
    Y_pred = (Y_prob >= args.threshold).astype(int)

    f1_micro = f1_score(Y_val, Y_pred, average="micro", zero_division=0)
    p_micro  = precision_score(Y_val, Y_pred, average="micro", zero_division=0)
    r_micro  = recall_score(Y_val, Y_pred, average="micro", zero_division=0)
    f1_macro = f1_score(Y_val, Y_pred, average="macro", zero_division=0)

    print(f"\n[result] TF-IDF baseline  threshold={args.threshold}")
    print(f"  micro — P={p_micro:.4f}  R={r_micro:.4f}  F1={f1_micro:.4f}")
    print(f"  macro — F1={f1_macro:.4f}")

    # Sweep de thresholds para encontrar el óptimo
    print("\n[sweep] F1-micro por threshold:")
    for thr in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6):
        p = (Y_prob >= thr).astype(int)
        f = f1_score(Y_val, p, average="micro", zero_division=0)
        print(f"  thr={thr:.1f}  F1-micro={f:.4f}")


if __name__ == "__main__":
    main()
