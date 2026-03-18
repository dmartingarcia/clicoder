"""
train.py — Flat multi-label CIE-10 classifier (RigoBERTa)

Entrena un único modelo de clasificación multi-label sobre los ~1767 códigos
CIE-10 presentes en el dataset CodiESP.  No hay jerarquía: una sola pasada
forward produce probabilidades para todos los códigos a la vez.

Modelo por defecto: BSC-LT/RigoBERTa  (DeBERTa-v2, ventana 4096 tokens)
  Equivalente a usar --model_name BSC-LT/RigoBERTa

Uso básico (desde la raíz del proyecto):
  python ai_engine/train.py

Con todas las opciones:
  python ai_engine/train.py \\
      --train_file   training/csv_import_scripts/codiesp_csvs/codiesp_D_source_train.csv \\
      --val_file     training/csv_import_scripts/codiesp_csvs/codiesp_D_source_validation.csv \\
      --cie10_file   training/csv_import_scripts/cie10-csvs/cie10-es-diagnoses.csv \\
      --output_dir   ai_engine/model \\
      --model_name   BSC-LT/RigoBERTa \\
      --max_length   1024 \\
      --epochs       20 \\
      --batch_size   4 \\
      --grad_accum   4 \\
      --device       auto
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import f1_score, precision_score, recall_score
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer, get_cosine_schedule_with_warmup
from transformers import logging as hf_logging

# Forzar progress bars y logging aunque no haya TTY
hf_logging.set_verbosity_info()
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "0")
os.environ.setdefault("TQDM_DISABLE", "0")


# ==================== CIE-10 METADATA ====================

CHAPTER_MAP = {
    "A": "I",    "B": "I",
    "C": "II",   "D": "II",
    "E": "IV",
    "F": "V",
    "G": "VI",
    "H": "VII",
    "I": "IX",
    "J": "X",
    "K": "XI",
    "L": "XII",
    "M": "XIII",
    "N": "XIV",
    "O": "XV",
    "P": "XVI",
    "Q": "XVII",
    "R": "XVIII",
    "S": "XIX",  "T": "XIX",
    "V": "XX",   "W": "XX",  "X": "XX",  "Y": "XX",
    "Z": "XXI",
}

CIE10_CHAPTERS = {
    "I":    {"name": "Ciertas enfermedades infecciosas y parasitarias"},
    "II":   {"name": "Neoplasias"},
    "III":  {"name": "Enfermedades de la sangre y órganos hematopoyéticos"},
    "IV":   {"name": "Enfermedades endocrinas, nutricionales y metabólicas"},
    "V":    {"name": "Trastornos mentales y del comportamiento"},
    "VI":   {"name": "Enfermedades del sistema nervioso"},
    "VII":  {"name": "Enfermedades del ojo y sus anexos"},
    "VIII": {"name": "Enfermedades del oído y de la apófisis mastoides"},
    "IX":   {"name": "Enfermedades del sistema circulatorio"},
    "X":    {"name": "Enfermedades del sistema respiratorio"},
    "XI":   {"name": "Enfermedades del aparato digestivo"},
    "XII":  {"name": "Enfermedades de la piel y del tejido subcutáneo"},
    "XIII": {"name": "Enfermedades del sistema osteomuscular"},
    "XIV":  {"name": "Enfermedades del aparato genitourinario"},
    "XV":   {"name": "Embarazo, parto y puerperio"},
    "XVI":  {"name": "Ciertas afecciones originadas en el período perinatal"},
    "XVII": {"name": "Malformaciones congénitas"},
    "XVIII":{"name": "Síntomas, signos y hallazgos anormales"},
    "XIX":  {"name": "Traumatismos, envenenamientos y otras consecuencias"},
    "XX":   {"name": "Causas externas de morbilidad y mortalidad"},
    "XXI":  {"name": "Factores que influyen en el estado de salud"},
}


def extract_chapter(code: str):
    return CHAPTER_MAP.get(code[0].upper()) if code else None


# ==================== DATA ====================

def truncate_code(code: str, full: bool) -> str:
    """'B86.93D' → 'B86' (block) o 'B86.93D' (full)."""
    return code if full else code[:3]


def parse_labels(label_str: str, full: bool = False):
    """'i10;e11.9' → ['I10', 'E11.9'] o ['I10', 'E11'] según full."""
    if pd.isna(label_str) or not str(label_str).strip():
        return []
    return [
        truncate_code(c.strip().upper(), full)
        for c in str(label_str).split(";")
        if c.strip()
    ]


def load_data(train_file, val_file):
    print(f"[data] train: {train_file}")
    train_df = pd.read_csv(train_file)
    print(f"[data] val:   {val_file}")
    val_df = pd.read_csv(val_file)

    for df, name in [(train_df, "train"), (val_df, "val")]:
        df.columns = df.columns.str.strip()
        for col in ("text", "labels"):
            if col not in df.columns:
                raise ValueError(f"Column '{col}' missing in {name} CSV")
        df.dropna(subset=["text", "labels"], inplace=True)

    print(f"[data] rows — train={len(train_df)}  val={len(val_df)}")
    return train_df, val_df


def build_encoders(train_df, full_codes: bool):
    codes = sorted({
        code
        for ls in train_df["labels"]
        for code in parse_labels(ls, full=full_codes)
    })
    code_to_idx = {c: i for i, c in enumerate(codes)}
    idx_to_code = {str(i): c for i, c in enumerate(codes)}
    print(f"[encoders] {len(codes)} unique codes  (mode={'full' if full_codes else 'block'})")
    return codes, code_to_idx, idx_to_code


class CIE10Dataset(Dataset):
    def __init__(self, texts, label_strings, tokenizer, max_length, code_to_idx, full_codes: bool):
        self.texts         = texts
        self.label_strings = label_strings
        self.tokenizer     = tokenizer
        self.max_length    = max_length
        self.code_to_idx   = code_to_idx
        self.num_labels    = len(code_to_idx)
        self.full_codes    = full_codes

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        enc = self.tokenizer(
            self.texts[idx],
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        vec = torch.zeros(self.num_labels, dtype=torch.float32)
        for code in parse_labels(self.label_strings[idx], full=self.full_codes):
            if code in self.code_to_idx:
                vec[self.code_to_idx[code]] = 1.0
        return {
            "input_ids":      enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "labels":         vec,
        }


# ==================== MODEL ====================

class FlatClassifier(nn.Module):
    """Single encoder + linear head for flat multi-label CIE-10 classification."""

    def __init__(self, model_name: str, num_codes: int, dropout: float = 0.1):
        super().__init__()
        self.encoder = _load_encoder(model_name)
        if hasattr(self.encoder, "gradient_checkpointing_enable"):
            self.encoder.gradient_checkpointing_enable()
        self.dropout    = nn.Dropout(dropout)
        self.classifier = nn.Linear(self.encoder.config.hidden_size, num_codes)


    def forward(self, input_ids, attention_mask):
        out = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        # CLS token ([0]) — works for BERT, RoBERTa, DeBERTa-v2 (RigoBERTa)
        cls = self.dropout(out.last_hidden_state[:, 0, :])
        return self.classifier(cls)


def _load_encoder(model_name: str):
    """Carga el encoder con la mejor implementación de atención disponible."""
    for impl in ("flash_attention_2", "sdpa", None):
        kwargs = {"attn_implementation": impl} if impl else {}
        try:
            encoder = AutoModel.from_pretrained(model_name, **kwargs)
            label = impl or "eager (default)"
            print(f"[model] attn_implementation={label}")
            return encoder
        except (ValueError, ImportError):
            continue
    raise RuntimeError(f"No se pudo cargar el encoder para {model_name}")


# ==================== TRAINING ====================

def evaluate(model, loader, device, threshold=0.5):
    """Devuelve dict con precision, recall y F1 en micro y macro."""
    model.eval()
    preds_all, targets_all = [], []
    ac = _autocast_ctx(device)
    with torch.no_grad(), ac:
        for batch in loader:
            logits = model(
                batch["input_ids"].to(device),
                batch["attention_mask"].to(device),
            )
            probs   = torch.sigmoid(logits).float().cpu().numpy()
            targets = batch["labels"].cpu().numpy()
            preds_all.append((probs >= threshold).astype(int))
            targets_all.append(targets)

    P = np.vstack(preds_all)
    T = np.vstack(targets_all)
    if T.sum() == 0:
        return {k: 0.0 for k in ("p_micro","r_micro","f1_micro","p_macro","r_macro","f1_macro")}
    return {
        "p_micro":  float(precision_score(T, P, average="micro", zero_division=0)),
        "r_micro":  float(recall_score   (T, P, average="micro", zero_division=0)),
        "f1_micro": float(f1_score       (T, P, average="micro", zero_division=0)),
        "p_macro":  float(precision_score(T, P, average="macro", zero_division=0)),
        "r_macro":  float(recall_score   (T, P, average="macro", zero_division=0)),
        "f1_macro": float(f1_score       (T, P, average="macro", zero_division=0)),
    }


def _autocast_ctx(device):
    """
    Devuelve un context manager de mixed precision según el device:
      - CUDA  → bfloat16 si está soportado, si no float16
      - CPU   → bfloat16 (soporte nativo en Apple Silicon e Intel AMX)
      - otros → no-op
    bfloat16 mantiene el mismo rango de exponente que float32 (8 bits),
    solo reduce la mantisa (7 bits vs 23), por lo que el modelo no sufre
    overflow/underflow. Los pesos del optimizador se quedan en float32.
    """
    if device.type == "cuda":
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        return torch.autocast(device_type="cuda", dtype=dtype)
    if device.type == "mps":
        # MPS soporta float16; bfloat16 no está disponible en Metal
        return torch.autocast(device_type="mps", dtype=torch.float16)
    if device.type == "cpu":
        # bfloat16 nativo en Apple Silicon (M1/M2/M3) e Intel con AMX
        return torch.autocast(device_type="cpu", dtype=torch.bfloat16)
    return torch.autocast(device_type="cpu", enabled=False)


def compute_pos_weight(train_loader, num_labels: int, device, cap: float = 50.0):
    """
    Calcula pos_weight por clase = (#negativos) / (#positivos) para BCEWithLogitsLoss.
    Con cap evitamos pesos extremos en códigos rarísimos.
    """
    pos_counts = torch.zeros(num_labels)
    total      = 0
    for batch in train_loader:
        pos_counts += batch["labels"].sum(dim=0)
        total      += batch["labels"].shape[0]
    neg_counts = total - pos_counts
    weight = (neg_counts / pos_counts.clamp(min=1)).clamp(max=cap)
    print(f"[loss] pos_weight media={weight.mean():.1f}  max={weight.max():.1f}  (cap={cap})")
    return weight.to(device)


def train(model, train_loader, val_loader, device, epochs, patience, grad_accum, pos_weight_cap=10.0):
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-6, weight_decay=0.01)

    # Scheduler counts optimizer steps (= batches / grad_accum)
    total_opt_steps = (len(train_loader) // grad_accum) * epochs
    warmup_steps    = max(1, int(0.1 * total_opt_steps))
    scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_opt_steps,
    )
    pos_weight = compute_pos_weight(train_loader, model.classifier.out_features, device, cap=pos_weight_cap)
    loss_fn    = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    autocast   = _autocast_ctx(device)

    best_f1      = -1.0
    best_state   = None
    no_improve   = 0
    history      = []  # [{epoch, train_loss, val_f1_micro, val_f1_macro}]
    epoch_times  = []  # segundos por época para ETA

    n_batches = len(train_loader)
    print(f"\n{'='*60}")
    print(f"  epochs={epochs}  patience={patience}  grad_accum={grad_accum}")
    print(f"  batches/epoch={n_batches}  opt_steps/epoch={n_batches//grad_accum}")
    print(f"{'='*60}")

    def fmt_seconds(s):
        s = int(s)
        h, m = divmod(s, 3600)
        m, s = divmod(m, 60)
        return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"

    train_start = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss  = 0.0
        epoch_start = time.time()
        step_times  = []
        optimizer.zero_grad()

        for step, batch in enumerate(train_loader, 1):
            step_start = time.time()
            with autocast:
                logits = model(
                    batch["input_ids"].to(device),
                    batch["attention_mask"].to(device),
                )
                loss = loss_fn(logits, batch["labels"].to(device)) / grad_accum
            loss.backward()
            epoch_loss += loss.item() * grad_accum

            if step % grad_accum == 0 or step == len(train_loader):
                nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

            step_times.append(time.time() - step_start)

            log_every = max(1, n_batches // 4)
            if step % log_every == 0:
                avg_step  = sum(step_times) / len(step_times)
                remaining = avg_step * (n_batches - step)
                print(f"  epoch {epoch}/{epochs}  step {step}/{n_batches}"
                      f"  loss={loss.item() * grad_accum:.4f}"
                      f"  {avg_step:.1f}s/step  epoch ETA {fmt_seconds(remaining)}")

        epoch_elapsed = time.time() - epoch_start
        epoch_times.append(epoch_elapsed)

        avg_loss = epoch_loss / n_batches
        m        = evaluate(model, val_loader, device)
        history.append({"epoch": epoch, "train_loss": avg_loss,
                        **{f"val_{k}": v for k, v in m.items()},
                        "epoch_seconds": round(epoch_elapsed, 1)})

        avg_epoch_time = sum(epoch_times) / len(epoch_times)
        epochs_left    = epochs - epoch
        total_eta      = avg_epoch_time * epochs_left
        elapsed_total  = time.time() - train_start

        print(f"  epoch {epoch}/{epochs}  loss={avg_loss:.4f}"
              f"  P={m['p_micro']:.3f}  R={m['r_micro']:.3f}  F1={m['f1_micro']:.3f} (micro)"
              f"  |  P={m['p_macro']:.3f}  R={m['r_macro']:.3f}  F1={m['f1_macro']:.3f} (macro)"
              f"  [{fmt_seconds(epoch_elapsed)}/epoch  elapsed {fmt_seconds(elapsed_total)}"
              f"  ETA {fmt_seconds(total_eta)}]")

        if m["f1_micro"] > best_f1:
            best_f1    = m["f1_micro"]
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            no_improve = 0
            print(f"  → new best: {best_f1:.4f}  (saved)")
        else:
            no_improve += 1
            print(f"  → no improvement ({no_improve}/{patience})")
            if no_improve >= patience:
                print("  Early stopping.")
                break

    print(f"\n  Best val F1-micro: {best_f1:.4f}")
    return best_state or model.state_dict(), history


# ==================== MAIN ====================

def main():
    script_dir = Path(__file__).resolve().parent
    data_dir   = script_dir / "../training/csv_import_scripts"

    parser = argparse.ArgumentParser(description="Train flat CIE-10 classifier (RigoBERTa)")
    parser.add_argument("--train_file",
        default=str(data_dir / "codiesp_csvs/codiesp_D_source_train.csv"))
    parser.add_argument("--val_file",
        default=str(data_dir / "codiesp_csvs/codiesp_D_source_validation.csv"))
    parser.add_argument("--cie10_file",
        default=str(data_dir / "cie10-csvs/cie10-es-diagnoses.csv"))
    parser.add_argument("--output_dir",
        default=str(script_dir / "model"))
    parser.add_argument("--model_name",  default="BSC-LT/RigoBERTa")
    parser.add_argument("--max_length",  type=int, default=1024)
    parser.add_argument("--epochs",      type=int, default=20)
    parser.add_argument("--batch_size",  type=int, default=4)
    parser.add_argument("--grad_accum",  type=int, default=4,
        help="Gradient accumulation steps (virtual batch = batch_size * grad_accum)")
    parser.add_argument("--patience",    type=int, default=5)
    parser.add_argument("--threshold",   type=float, default=0.2)
    parser.add_argument("--device",      default="auto")
    parser.add_argument("--full_codes",  action="store_true",
        help="Usar código completo (B86.93D). Por defecto: solo bloque (B86)")
    parser.add_argument("--pos_weight_cap", type=float, default=10.0,
        help="Cap máximo para pos_weight por clase (default: 10.0). "
             "Valores altos (>=50) sobrepenalizan falsos negativos y producen recall alto pero precision baja.")
    args = parser.parse_args()

    # Device — prioridad: CUDA > MPS (Apple GPU) > CPU
    if args.device == "auto":
        if torch.cuda.is_available():
            device = torch.device("cuda")
        elif torch.backends.mps.is_available():
            device = torch.device("mps")
        else:
            device = torch.device("cpu")
    else:
        device = torch.device(args.device)
    print(f"\n[setup] device={device}  model={args.model_name}  max_length={args.max_length}")

    # Data
    train_df, val_df = load_data(args.train_file, args.val_file)
    codes, code_to_idx, idx_to_code = build_encoders(train_df, full_codes=args.full_codes)

    # CIE-10 catalog (descriptions)
    code_descriptions = {}
    if os.path.exists(args.cie10_file):
        cie_df = pd.read_csv(args.cie10_file)
        cie_df.columns = cie_df.columns.str.strip()
        if "code" in cie_df.columns and "description" in cie_df.columns:
            code_descriptions = {
                str(r["code"]).strip().upper(): str(r["description"]).strip()
                for _, r in cie_df.iterrows()
            }
            print(f"[data] {len(code_descriptions)} code descriptions loaded")
        else:
            print(f"[warn] CIE-10 catalog unexpected columns: {list(cie_df.columns)}")
    else:
        print(f"[warn] CIE-10 file not found: {args.cie10_file}")

    # Tokenizer
    print(f"\n[model] Loading tokenizer …")
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)

    # Datasets
    def make_loader(df, shuffle):
        ds = CIE10Dataset(
            df["text"].tolist(), df["labels"].tolist(),
            tokenizer, args.max_length, code_to_idx,
            full_codes=args.full_codes,
        )
        return DataLoader(ds, batch_size=args.batch_size, shuffle=shuffle, num_workers=2)

    train_loader = make_loader(train_df, shuffle=True)
    val_loader   = make_loader(val_df,   shuffle=False)

    # Model
    print(f"[model] Initialising FlatClassifier ({len(codes)} codes) …")
    model = FlatClassifier(args.model_name, num_codes=len(codes)).to(device)
    ctx   = _autocast_ctx(device)
    _dtype = getattr(ctx, "_dtype", "bfloat16")
    print(f"[model] mixed precision: {_dtype} autocast en {device.type}")

    # Train
    best_state, history = train(
        model, train_loader, val_loader, device,
        epochs=args.epochs, patience=args.patience, grad_accum=args.grad_accum,
        pos_weight_cap=args.pos_weight_cap,
    )

    # Save
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[save] Writing artifacts → {output_dir.resolve()}")

    with open(output_dir / "config.json", "w") as f:
        json.dump({
            "model_name": args.model_name,
            "max_length": args.max_length,
            "threshold":  args.threshold,
            "full_codes": args.full_codes,
        }, f, indent=2)
    print("[save] config.json")

    with open(output_dir / "cie10_chapters.json", "w", encoding="utf-8") as f:
        json.dump(CIE10_CHAPTERS, f, ensure_ascii=False, indent=2)
    print("[save] cie10_chapters.json")

    torch.save({
        "code_to_idx":      code_to_idx,
        "idx_to_code":      idx_to_code,
        "model_state_dict": best_state,
    }, output_dir / "classifier.pt")
    print("[save] classifier.pt")

    with open(output_dir / "code_descriptions.json", "w", encoding="utf-8") as f:
        json.dump(code_descriptions, f, ensure_ascii=False, indent=2)
    print("[save] code_descriptions.json")

    # Final eval con el mejor modelo
    model.load_state_dict(best_state)
    model.to(device)
    fm = evaluate(model, val_loader, device, threshold=args.threshold)
    print(f"\n[result] threshold={args.threshold}")
    print(f"  micro — P={fm['p_micro']:.4f}  R={fm['r_micro']:.4f}  F1={fm['f1_micro']:.4f}")
    print(f"  macro — P={fm['p_macro']:.4f}  R={fm['r_macro']:.4f}  F1={fm['f1_macro']:.4f}")

    # ---- CSV de run ----
    import csv
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs_csv  = output_dir / "training_runs.csv"
    row = {
        "timestamp":    timestamp,
        "model_name":   args.model_name,
        "full_codes":   args.full_codes,
        "max_length":   args.max_length,
        "epochs_run":   len(history),
        "epochs_max":   args.epochs,
        "batch_size":   args.batch_size,
        "grad_accum":   args.grad_accum,
        "patience":     args.patience,
        "threshold":      args.threshold,
        "pos_weight_cap": args.pos_weight_cap,
        "train_rows":   len(train_df),
        "val_rows":     len(val_df),
        "num_codes":    len(codes),
        "val_p_micro":  round(fm["p_micro"],  6),
        "val_r_micro":  round(fm["r_micro"],  6),
        "val_f1_micro": round(fm["f1_micro"], 6),
        "val_p_macro":  round(fm["p_macro"],  6),
        "val_r_macro":  round(fm["r_macro"],  6),
        "val_f1_macro": round(fm["f1_macro"], 6),
        "total_seconds":     round(sum(h["epoch_seconds"] for h in history), 1),
        "avg_epoch_seconds": round(sum(h["epoch_seconds"] for h in history) / len(history), 1),
    }
    write_header = not runs_csv.exists()
    with open(runs_csv, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    print(f"[save] training_runs.csv  (append)")

    # ---- Gráfica ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    epochs_x = [h["epoch"]           for h in history]
    losses   = [h["train_loss"]      for h in history]
    p_micro  = [h["val_p_micro"]     for h in history]
    r_micro  = [h["val_r_micro"]     for h in history]
    f1_micro = [h["val_f1_micro"]    for h in history]
    f1_macro = [h["val_f1_macro"]    for h in history]

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 11), sharex=True)

    ax1.plot(epochs_x, losses, marker="o", color="steelblue", label="train loss")
    ax1.set_ylabel("Loss")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(epochs_x, p_micro, marker="^", color="royalblue",  label="Precision (micro)")
    ax2.plot(epochs_x, r_micro, marker="v", color="tomato",     label="Recall (micro)")
    ax2.plot(epochs_x, f1_micro, marker="o", color="seagreen",  label="F1 (micro)", linewidth=2)
    ax2.set_ylabel("micro")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    ax3.plot(epochs_x, f1_micro, marker="o", color="seagreen",   label="F1-micro")
    ax3.plot(epochs_x, f1_macro, marker="s", color="darkorange",  label="F1-macro")
    ax3.set_ylabel("F1 micro vs macro")
    ax3.set_xlabel("Epoch")
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    fig.suptitle(f"{args.model_name} — {timestamp}\n"
                 f"F1-micro={fm['f1_micro']:.4f}  P={fm['p_micro']:.4f}  R={fm['r_micro']:.4f}"
                 f"  |  F1-macro={fm['f1_macro']:.4f}")
    plt.tight_layout()
    plot_path = output_dir / f"training_curve_{timestamp}.png"
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    print(f"[save] {plot_path.name}")

    print("[done]")


if __name__ == "__main__":
    main()
