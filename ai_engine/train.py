"""
train.py — Flat multi-label CIE-10 classifier (RigoBERTa-Clinical)

Entrena un único modelo de clasificación multi-label sobre los ~1767 códigos
CIE-10 presentes en el dataset CodiESP.  No hay jerarquía: una sola pasada
forward produce probabilidades para todos los códigos a la vez.

Modelo por defecto: IIC/RigoBERTa-Clinical  (XLM-RoBERTa-large, especialización clínica ES)
  Equivalente a usar --model_name IIC/RigoBERTa-Clinical

Uso básico (desde la raíz del proyecto):
  python ai_engine/train.py

Con todas las opciones:
  python ai_engine/train.py \\
      --train_file   training/csv_import_scripts/codiesp_csvs/codiesp_D_source_train.csv \\
      --val_file     training/csv_import_scripts/codiesp_csvs/codiesp_D_source_validation.csv \\
      --cie10_file   training/csv_import_scripts/cie10-csvs/cie10-es-diagnoses.csv \\
      --output_dir   ai_engine/model \\
      --model_name   IIC/RigoBERTa-Clinical \\
      --max_length   1024 \\
      --epochs       20 \\
      --batch_size   4 \\
      --grad_accum   4 \\
      --device       auto
"""

import argparse
import json
import os
import random
import time
from contextlib import contextmanager
from datetime import UTC
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
)
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer, get_cosine_schedule_with_warmup
from transformers import logging as hf_logging

# Forzar progress bars y logging aunque no haya TTY
hf_logging.set_verbosity_info()
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "0")
os.environ.setdefault("TQDM_DISABLE", "0")


# ==================== CIE-10 METADATA ====================

# Rangos de categoría (3 caracteres) → capítulo CIE-10. La letra inicial no basta: la D se
# reparte entre neoplasias (C00-D49) y sangre (D50-D89), y la H entre ojo (H00-H59) y oído
# (H60-H95). Debe mantenerse en sincronía con CHAPTER_RANGES de classifier.py.
CHAPTER_RANGES: list[tuple[str, str, str]] = [
    ("I", "A00", "B99"),
    ("II", "C00", "D49"),
    ("III", "D50", "D89"),
    ("IV", "E00", "E89"),
    ("V", "F01", "F99"),
    ("VI", "G00", "G99"),
    ("VII", "H00", "H59"),
    ("VIII", "H60", "H95"),
    ("IX", "I00", "I99"),
    ("X", "J00", "J99"),
    ("XI", "K00", "K95"),
    ("XII", "L00", "L99"),
    ("XIII", "M00", "M99"),
    ("XIV", "N00", "N99"),
    ("XV", "O00", "O9A"),
    ("XVI", "P00", "P96"),
    ("XVII", "Q00", "Q99"),
    ("XVIII", "R00", "R99"),
    ("XIX", "S00", "T88"),
    ("XX", "V00", "Y99"),
    ("XXI", "Z00", "Z99"),
    ("XXII", "U00", "U85"),
]

CIE10_CHAPTERS = {
    "I": {"name": "Ciertas enfermedades infecciosas y parasitarias"},
    "II": {"name": "Neoplasias"},
    "III": {"name": "Enfermedades de la sangre y órganos hematopoyéticos"},
    "IV": {"name": "Enfermedades endocrinas, nutricionales y metabólicas"},
    "V": {"name": "Trastornos mentales y del comportamiento"},
    "VI": {"name": "Enfermedades del sistema nervioso"},
    "VII": {"name": "Enfermedades del ojo y sus anexos"},
    "VIII": {"name": "Enfermedades del oído y de la apófisis mastoides"},
    "IX": {"name": "Enfermedades del sistema circulatorio"},
    "X": {"name": "Enfermedades del sistema respiratorio"},
    "XI": {"name": "Enfermedades del aparato digestivo"},
    "XII": {"name": "Enfermedades de la piel y del tejido subcutáneo"},
    "XIII": {"name": "Enfermedades del sistema osteomuscular"},
    "XIV": {"name": "Enfermedades del aparato genitourinario"},
    "XV": {"name": "Embarazo, parto y puerperio"},
    "XVI": {"name": "Ciertas afecciones originadas en el período perinatal"},
    "XVII": {"name": "Malformaciones congénitas"},
    "XVIII": {"name": "Síntomas, signos y hallazgos anormales"},
    "XIX": {"name": "Traumatismos, envenenamientos y otras consecuencias"},
    "XX": {"name": "Causas externas de morbilidad y mortalidad"},
    "XXI": {"name": "Factores que influyen en el estado de salud"},
    "XXII": {"name": "Códigos para propósitos especiales"},
}


def extract_chapter(code: str):
    """Capítulo CIE-10 de un código, resolviendo los rangos que comparten letra inicial."""
    if not code:
        return None
    category = code.strip().upper()[:3].ljust(3, "0")
    for chapter, lo, hi in CHAPTER_RANGES:
        if lo <= category <= hi:
            return chapter
    return None


# ==================== DATA ====================


def truncate_code(code: str, full: bool) -> str:
    """'B86.93D' → 'B86' (block) o 'B86.93D' (full)."""
    return code if full else code[:3]


def parse_labels(label_str: str, full: bool = False, chapters: bool = False):
    """'i10;e11.9' → capítulos ['IX'] o bloques ['I10', 'E11'] o full codes."""
    if pd.isna(label_str) or not str(label_str).strip():
        return []
    codes = [c.strip().upper() for c in str(label_str).split(";") if c.strip()]
    if chapters:
        return list({ch for c in codes if (ch := extract_chapter(c))})
    return [truncate_code(c, full) for c in codes]


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


def build_encoders(train_df, full_codes: bool, chapters: bool = False):
    codes = sorted(
        {
            code
            for ls in train_df["labels"]
            for code in parse_labels(ls, full=full_codes, chapters=chapters)
        }
    )
    code_to_idx = {c: i for i, c in enumerate(codes)}
    idx_to_code = {str(i): c for i, c in enumerate(codes)}
    mode = "chapters" if chapters else ("full" if full_codes else "block")
    print(f"[encoders] {len(codes)} unique codes  (mode={mode})")
    return codes, code_to_idx, idx_to_code


class CIE10Dataset(Dataset):
    def __init__(
        self,
        texts,
        label_strings,
        tokenizer,
        max_length,
        code_to_idx,
        full_codes: bool,
        chapters: bool = False,
        sliding_window: bool = False,
        chunk_overlap: int = 64,
        teacher_probs=None,
    ):
        self.texts = texts
        self.label_strings = label_strings
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.code_to_idx = code_to_idx
        self.num_labels = len(code_to_idx)
        self.full_codes = full_codes
        self.chapters = chapters
        self.sliding_window = sliding_window  # True → encode full text as overlapping chunks
        self.chunk_overlap = chunk_overlap  # stride in tokens between consecutive chunks
        # (n_docs, num_labels) con las probabilidades del profesor, o None si no hay destilación
        self.teacher_probs = teacher_probs

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        if self.sliding_window:
            # Tokenize the full text as overlapping windows of max_length tokens.
            # Returns (num_chunks, max_length) where num_chunks >= 1.
            enc = self.tokenizer(
                self.texts[idx],
                max_length=self.max_length,
                stride=self.chunk_overlap,
                padding="max_length",
                truncation=True,
                return_overflowing_tokens=True,
                return_tensors="pt",
            )
            input_ids = enc["input_ids"]  # (num_chunks, max_length)
            attention_mask = enc["attention_mask"]  # (num_chunks, max_length)
        else:
            enc = self.tokenizer(
                self.texts[idx],
                max_length=self.max_length,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )
            input_ids = enc["input_ids"].squeeze(0)  # (max_length,)
            attention_mask = enc["attention_mask"].squeeze(0)  # (max_length,)

        vec = torch.zeros(self.num_labels, dtype=torch.float32)
        for code in parse_labels(
            self.label_strings[idx], full=self.full_codes, chapters=self.chapters
        ):
            if code in self.code_to_idx:
                vec[self.code_to_idx[code]] = 1.0
        item = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": vec,
        }
        if self.teacher_probs is not None:
            item["teacher"] = torch.from_numpy(self.teacher_probs[idx])
        return item


def build_pretrain_loader(
    cie10_file,
    tokenizer,
    max_length,
    code_to_idx,
    full_codes,
    batch_size,
    taskx_files=None,
):
    """Genera un DataLoader para pre-entrenamiento combinando dos fuentes:

    Fuente 1 — descripciones oficiales CIE-10 (csv cie10_file):
      Cada fila puede tener variantes separadas por '|' en la columna 'description'.
      Cada variante se convierte en una muestra con su código como única etiqueta.
      Solo se incluyen códigos presentes en code_to_idx (vocabulario CodiESP).

    Fuente 2 — snippets clínicos reales (task_X CSVs, opcional):
      Columna 'task_x' contiene JSON con anotaciones de explainabilidad CodiESP.
      Se extraen solo las anotaciones DIAGNOSTICO: cada snippet de texto clínico
      (jerga, siglas, variantes) se empareja con su código como muestra de pretrain.
    """
    cie_df = pd.read_csv(cie10_file)
    cie_df.columns = cie_df.columns.str.strip()
    texts, label_strings = [], []
    seen_codes = set()

    # Fuente 1: descripciones oficiales CIE-10
    for _, row in cie_df.iterrows():
        raw_code = str(row["code"]).strip().upper()
        code = raw_code if full_codes else raw_code[:3]
        if code not in code_to_idx:
            continue
        seen_codes.add(code)
        desc = str(row.get("description", "")).strip()
        for variant in desc.split("|"):
            variant = variant.strip()
            if variant:
                texts.append(variant)
                label_strings.append(code)
    print(
        f"[pretrain] CIE-10 descriptions: {len(texts)} variantes  ({len(seen_codes)} códigos únicos)"
    )

    # Fuente 2: snippets clínicos task_X (DIAGNOSTICO)
    if taskx_files:
        import ast

        n_before = len(texts)
        taskx_codes: set = set()
        for taskx_file in taskx_files:
            try:
                tx_df = pd.read_csv(taskx_file)
                tx_df.columns = tx_df.columns.str.strip()
                for _, row in tx_df.iterrows():
                    try:
                        # task_x está almacenado como Python dict literal (comillas simples),
                        # no como JSON estándar — usar ast.literal_eval en vez de json.loads
                        annotations = ast.literal_eval(str(row.get("task_x", "[]")))
                    except (ValueError, SyntaxError):
                        continue
                    for ann in annotations:
                        if ann.get("label") != "DIAGNOSTICO":
                            continue
                        snippet = str(ann.get("text", "")).strip()
                        if not snippet:
                            continue
                        raw_code = str(ann.get("code", "")).strip().upper()
                        code = raw_code if full_codes else raw_code[:3]
                        if code not in code_to_idx:
                            continue
                        taskx_codes.add(code)
                        texts.append(snippet)
                        label_strings.append(code)
            except Exception as e:
                print(f"[pretrain] warning: no se pudo cargar {taskx_file}: {e}")
        n_taskx = len(texts) - n_before
        print(
            f"[pretrain] task_X snippets:  {n_taskx} snippets  ({len(taskx_codes)} códigos únicos)"
        )

    print(f"[pretrain] total: {len(texts)} muestras")
    ds = CIE10Dataset(
        texts,
        label_strings,
        tokenizer,
        max_length,
        code_to_idx,
        full_codes=full_codes,
        chapters=False,
    )
    return DataLoader(ds, batch_size=batch_size, shuffle=True, num_workers=2)


def pretrain(model, pretrain_loader, device, epochs, lr, weight_decay):
    """Pre-entrenamiento sobre descripciones CIE-10 (sin early stopping ni eval en val).

    El objetivo es que el encoder aprenda a asociar terminología clínica con códigos
    antes del fine-tuning sobre CodiESP.
    """
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    loss_fn = nn.BCEWithLogitsLoss()
    autocast = _autocast_ctx(device)
    n = len(pretrain_loader.dataset)
    print(f"\n{'=' * 60}")
    print(f"[pretrain] {n} muestras  epochs={epochs}  lr={lr}")
    print(f"{'=' * 60}")
    import time as _time

    n_batches = len(pretrain_loader)
    epoch_times = []
    pretrain_start = _time.time()

    def _fmt(s):
        s = int(s)
        h, m = divmod(s, 3600)
        m, s = divmod(m, 60)
        return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        step_times = []
        epoch_start = _time.time()
        for step, batch in enumerate(pretrain_loader):
            step_start = _time.time()
            optimizer.zero_grad()
            with autocast:
                logits = model(batch["input_ids"].to(device), batch["attention_mask"].to(device))
                loss = loss_fn(logits, batch["labels"].to(device))
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            total_loss += loss.item()
            step_times.append(_time.time() - step_start)
            log_every = max(1, n_batches // 4)
            is_last = step == n_batches - 1
            if step % log_every == 0 or is_last:
                avg_step = sum(step_times) / len(step_times)
                print(
                    f"  pretrain {epoch}/{epochs}  step {step}/{n_batches}"
                    f"  loss={loss.item():.4f}  {avg_step:.2f}s/step"
                    f"  epoch ETA {_fmt(avg_step * (n_batches - step))}"
                )
        epoch_elapsed = _time.time() - epoch_start
        epoch_times.append(epoch_elapsed)
        avg_loss = total_loss / n_batches
        avg_epoch = sum(epoch_times) / len(epoch_times)
        total_eta = avg_epoch * (epochs - epoch)
        elapsed = _time.time() - pretrain_start
        print(
            f"  pretrain {epoch}/{epochs}  loss={avg_loss:.4f}"
            f"  [{_fmt(epoch_elapsed)}/epoch  elapsed {_fmt(elapsed)}  ETA {_fmt(total_eta)}]"
        )
    print("[pretrain] completado\n")


def sliding_window_collate(batch):
    """Collate function for sliding window mode.

    Each sample has input_ids of shape (num_chunks, max_length). Concatenates all
    chunks and tracks how many chunks belong to each document via doc_chunk_counts.
    """
    all_ids = torch.cat([item["input_ids"] for item in batch], dim=0)
    all_masks = torch.cat([item["attention_mask"] for item in batch], dim=0)
    counts = torch.tensor([item["input_ids"].shape[0] for item in batch])
    labels = torch.stack([item["labels"] for item in batch])
    return {
        "input_ids": all_ids,  # (total_chunks, max_length)
        "attention_mask": all_masks,  # (total_chunks, max_length)
        "doc_chunk_counts": counts,  # (batch_size,)
        "labels": labels,  # (batch_size, num_labels)
    }


# ==================== MODEL ====================


class FlatClassifier(nn.Module):
    """Single encoder + linear head for flat multi-label CIE-10 classification."""

    def __init__(
        self,
        model_name: str,
        num_codes: int,
        dropout: float = 0.1,
        freeze_layers: int = 0,
    ):
        super().__init__()
        self.encoder, self.attn_impl = _load_encoder(model_name)
        # Longformer requiere global_attention_mask con atención global en el CLS (pos 0)
        self.is_longformer = hasattr(self.encoder.config, "attention_window")
        self._apply_freeze(freeze_layers)
        self.current_freeze = freeze_layers  # rastreado para progressive unfreezing
        if hasattr(self.encoder, "gradient_checkpointing_enable"):
            self.encoder.gradient_checkpointing_enable()
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(self.encoder.config.hidden_size, num_codes)

    def _apply_freeze(self, freeze_layers: int):
        if freeze_layers <= 0:
            return
        # Congelar embeddings siempre que se congelen capas
        for param in self.encoder.embeddings.parameters():
            param.requires_grad = False
        # Detectar lista de capas (encoder.layer para RoBERTa/BERT,
        # encoder.layers para modelos DeBERTa)
        layers = None
        if hasattr(self.encoder, "encoder"):
            enc = self.encoder.encoder
            if hasattr(enc, "layer"):
                layers = enc.layer
            elif hasattr(enc, "layers"):
                layers = enc.layers
        if layers is None:
            print(f"[model] freeze_layers={freeze_layers}: arquitectura no reconocida, se omite")
            return
        total = len(layers)
        n = min(freeze_layers, total)
        for layer in layers[:n]:
            for param in layer.parameters():
                param.requires_grad = False
        trainable = sum(p.numel() for p in self.encoder.parameters() if p.requires_grad)
        total_p = sum(p.numel() for p in self.encoder.parameters())
        print(
            f"[model] freeze_layers={n}/{total}  encoder trainable: {trainable / 1e6:.1f}M / {total_p / 1e6:.1f}M params"
        )

    def _get_encoder_layers(self):
        if hasattr(self.encoder, "encoder"):
            enc = self.encoder.encoder
            if hasattr(enc, "layer"):
                return enc.layer
            elif hasattr(enc, "layers"):
                return enc.layers
        return None

    def unfreeze_next_group(self, n_layers: int):
        """Descongela las siguientes n_layers capas congeladas (las de mayor índice, más semánticas).

        Devuelve lista de parámetros recién activados para añadir como nuevo param group
        al optimizador con LR reducido. Actualiza self.current_freeze.
        """
        if self.current_freeze <= 0:
            return []
        layers = self._get_encoder_layers()
        if layers is None:
            return []
        n = min(n_layers, self.current_freeze)
        new_start = self.current_freeze - n
        new_params = []
        for layer in layers[new_start : self.current_freeze]:
            for param in layer.parameters():
                if not param.requires_grad:
                    param.requires_grad = True
                    new_params.append(param)
        self.current_freeze = new_start
        trainable = sum(p.numel() for p in self.encoder.parameters() if p.requires_grad)
        total_p = sum(p.numel() for p in self.encoder.parameters())
        print(
            f"[unfreeze] capas {new_start}–{new_start + n - 1} activadas  "
            f"freeze_layers→{self.current_freeze}  "
            f"encoder trainable: {trainable / 1e6:.1f}M/{total_p / 1e6:.1f}M  "
            f"nuevos params: {sum(p.numel() for p in new_params) / 1e6:.1f}M"
        )
        return new_params

    def forward(self, input_ids, attention_mask, doc_chunk_counts=None):
        kwargs = {}
        if self.is_longformer:
            # CLS (posición 0) necesita atención global para ver todo el documento
            gam = torch.zeros_like(input_ids)
            gam[:, 0] = 1
            kwargs["global_attention_mask"] = gam
        out = self.encoder(input_ids=input_ids, attention_mask=attention_mask, **kwargs)
        # CLS token ([0]) — works for BERT, RoBERTa, DeBERTa-v2, Longformer
        cls = out.last_hidden_state[:, 0, :]  # (total_chunks, hidden_size)

        if doc_chunk_counts is not None:
            # Sliding window: mean-pool chunk embeddings per document
            pooled = []
            start = 0
            for n in doc_chunk_counts.tolist():
                pooled.append(cls[start : start + n].mean(dim=0))
                start += n
            cls = torch.stack(pooled)  # (batch_size, hidden_size)

        return self.classifier(self.dropout(cls))


def _load_encoder(model_name: str):
    """Carga el encoder con la mejor implementación de atención disponible.
    Devuelve (encoder, attn_label) donde attn_label es el impl seleccionado."""
    for impl in ("flash_attention_2", "sdpa", None):
        # flash_attention_2 requiere bfloat16; sdpa y eager funcionan en float32
        kwargs = {"attn_implementation": impl} if impl else {}
        if impl == "flash_attention_2":
            kwargs["torch_dtype"] = torch.bfloat16
        try:
            encoder = AutoModel.from_pretrained(model_name, **kwargs)
            # Cargar en bfloat16 satisface el check de transformers para flash_attention_2,
            # pero los parámetros deben estar en float32 para que el optimizador (Adam)
            # mantenga sus estados en float32. Flash attention sigue activo en runtime
            # porque attn_implementation queda grabado en el config del modelo;
            # autocast provee tensores bfloat16 durante el forward.
            if impl == "flash_attention_2":
                encoder = encoder.to(torch.float32)
            label = impl or "eager"
            print(f"[model] attn_implementation={label}")
            return encoder, label
        except (ValueError, ImportError):
            continue
    raise RuntimeError(f"No se pudo cargar el encoder para {model_name}")


# ==================== TRAINING ====================


def _collect_probs(model, loader, device):
    """Pasada de inferencia sobre loader. Devuelve (probs, targets) como arrays numpy."""
    model.eval()
    probs_all, targets_all = [], []
    ac = _autocast_ctx(device)
    with torch.no_grad(), ac:
        for batch in loader:
            logits = model(
                batch["input_ids"].to(device),
                batch["attention_mask"].to(device),
                doc_chunk_counts=batch.get("doc_chunk_counts"),
            )
            probs_all.append(torch.sigmoid(logits).float().cpu().numpy())
            targets_all.append(batch["labels"].cpu().numpy())
    return np.vstack(probs_all), np.vstack(targets_all)


def find_optimal_threshold(model, loader, device, low=0.05, high=0.95, steps=19):
    """Barre threshold global en el val set para maximizar F1-micro.

    No modifica el modelo. Devuelve (best_thr, best_f1).
    """
    probs, T = _collect_probs(model, loader, device)
    best_thr, best_f1 = 0.5, -1.0
    for thr in np.linspace(low, high, steps):
        P = (probs >= thr).astype(int)
        f1 = float(f1_score(T, P, average="micro", zero_division=0))
        if f1 > best_f1:
            best_f1, best_thr = f1, float(thr)
    return round(best_thr, 4), round(best_f1, 6)


def find_optimal_thresholds_per_class(
    probs, T, global_thr, min_val_positives=2, low=0.05, high=0.95, steps=19
):
    """Threshold óptimo por clase para maximizar F1 binario de cada código.

    Para clases con menos de `min_val_positives` positivos en val (umbral no fiable),
    usa el threshold global en vez del específico — evita que un umbral=0.05 dispare
    falsos positivos en códigos rarísimos y destruya F1-micro.

    Devuelve array de shape (num_classes,) con el threshold óptimo de cada clase.
    """
    num_classes = T.shape[1]
    thresholds = np.full(num_classes, global_thr, dtype=np.float32)
    sweep = np.linspace(low, high, steps)
    n_optimized = 0
    for c in range(num_classes):
        if T[:, c].sum() < min_val_positives:
            continue  # insuficientes positivos en val → mantener threshold global
        best_f1, best_thr = -1.0, global_thr
        for thr in sweep:
            p = (probs[:, c] >= thr).astype(int)
            f1 = float(f1_score(T[:, c], p, average="binary", zero_division=0))
            if f1 > best_f1:
                best_f1, best_thr = f1, thr
        thresholds[c] = best_thr
        n_optimized += 1
    print(
        f"[threshold/clase] optimizadas={n_optimized}/{num_classes}  "
        f"(fallback global={global_thr:.2f} para {num_classes - n_optimized} clases "
        f"con <{min_val_positives} positivos en val)"
    )
    return thresholds


def _map_codiesp(T, PROBS):
    """MAP estilo CodiEsp: per-documento (TREC-style).
    Para cada nota, ordena los códigos por score y calcula AP de los correctos.
    Solo documentos con al menos un código positivo contribuyen a la media.
    Directamente comparable con el MAP del benchmark CodiEsp (best≈0.48).
    """
    aps = [float(average_precision_score(T[i], PROBS[i])) for i in range(len(T)) if T[i].sum() > 0]
    return float(np.mean(aps)) if aps else 0.0


def evaluate(model, loader, device, threshold=0.5):
    """Devuelve dict con precision, recall, F1 (micro y macro) y MAP macro."""
    model.eval()
    probs_all, preds_all, targets_all = [], [], []
    ac = _autocast_ctx(device)
    with torch.no_grad(), ac:
        for batch in loader:
            logits = model(
                batch["input_ids"].to(device),
                batch["attention_mask"].to(device),
                doc_chunk_counts=batch.get("doc_chunk_counts"),
            )
            probs = torch.sigmoid(logits).float().cpu().numpy()
            targets = batch["labels"].cpu().numpy()
            probs_all.append(probs)
            preds_all.append((probs >= threshold).astype(int))
            targets_all.append(targets)

    P = np.vstack(preds_all)
    T = np.vstack(targets_all)
    PROBS = np.vstack(probs_all)
    if T.sum() == 0:
        return {
            k: 0.0
            for k in (
                "p_micro",
                "r_micro",
                "f1_micro",
                "p_macro",
                "r_macro",
                "f1_macro",
                "map_macro",
            )
        }
    return {
        "p_micro": float(precision_score(T, P, average="micro", zero_division=0)),
        "r_micro": float(recall_score(T, P, average="micro", zero_division=0)),
        "f1_micro": float(f1_score(T, P, average="micro", zero_division=0)),
        "p_macro": float(precision_score(T, P, average="macro", zero_division=0)),
        "r_macro": float(recall_score(T, P, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(T, P, average="macro", zero_division=0)),
        "map_macro": _map_codiesp(T, PROBS),
    }


def compute_teacher_probs(
    ckpt_paths, texts, tokenizer, model_name, max_length, batch_size, device, code_to_idx
):
    """Promedio de las probabilidades de varios checkpoints sobre `texts` (destilación).

    Los checkpoints deben compartir exactamente el espacio de códigos del run actual;
    si no, el promedio mezclaría índices que representan códigos distintos.
    """
    n = len(texts)
    acc = np.zeros((n, len(code_to_idx)), dtype=np.float32)
    for path in ckpt_paths:
        print(f"[distill] profesor: {os.path.basename(path)}")
        ck = torch.load(path, map_location="cpu", weights_only=False)
        if ck["code_to_idx"] != code_to_idx:
            raise ValueError(
                f"{os.path.basename(path)} tiene un espacio de códigos distinto al de este run; "
                "no se puede promediar."
            )
        teacher = FlatClassifier(model_name, len(code_to_idx), dropout=0.0, freeze_layers=0)
        teacher.load_state_dict(ck["model_state_dict"])
        teacher.to(device).eval()
        with torch.no_grad(), _autocast_ctx(device):
            for i in range(0, n, batch_size):
                chunk = texts[i : i + batch_size]
                enc = tokenizer(
                    chunk,
                    max_length=max_length,
                    padding="max_length",
                    truncation=True,
                    return_tensors="pt",
                )
                logits = teacher(enc["input_ids"].to(device), enc["attention_mask"].to(device))
                acc[i : i + len(chunk)] += torch.sigmoid(logits).float().cpu().numpy()
        del teacher, ck
        if device.type == "cuda":
            torch.cuda.empty_cache()
    acc /= len(ckpt_paths)
    print(f"[distill] {len(ckpt_paths)} profesores promediados sobre {n} documentos")
    return acc


def _previous_bests(runs_csv):
    """Mejor val_f1_micro y mejor val_map_macro registrados hasta ahora en el CSV de runs."""
    import csv as _csv

    best = {"f1": None, "map": None}
    if not runs_csv.exists():
        return best
    with open(runs_csv, newline="") as f:
        for r in _csv.DictReader(f):
            r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
            for key, col in (("f1", "val_f1_micro"), ("map", "val_map_macro")):
                try:
                    v = float(r.get(col, ""))
                except ValueError:
                    continue
                if best[key] is None or v > best[key]:
                    best[key] = v
    return best


def push_to_hub(output_dir, model_filename, thresholds_filename, repo_id):
    """Publica el checkpoint como classifier.pt en el repo de Hugging Face.

    Mismos nombres de destino que `make model-upload`, para que `make model-download`
    y el arranque del motor sigan encontrando los artefactos donde esperan.
    """
    import os

    from huggingface_hub import HfApi

    token = os.environ.get("HUGGING_FACE_HUB_TOKEN") or os.environ.get("HF_TOKEN")
    if not token:
        print("[hub] ERROR: sin HUGGING_FACE_HUB_TOKEN en el entorno; no se publica")
        return
    api = HfApi(token=token)
    uploads = [
        (output_dir / model_filename, "classifier.pt"),
        (output_dir / thresholds_filename, "thresholds.json"),
        (output_dir / "code_descriptions.json", "code_descriptions.json"),
    ]
    for local, remote in uploads:
        if not local.exists():
            print(f"[hub] aviso: falta {local.name}, se omite")
            continue
        print(f"[hub] subiendo {local.name} → {repo_id}/{remote}")
        api.upload_file(
            path_or_fileobj=str(local), path_in_repo=remote, repo_id=repo_id, repo_type="model"
        )
    print(f"[hub] publicado: https://huggingface.co/{repo_id}")


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


class AsymmetricLoss(nn.Module):
    """
    Asymmetric Loss para multi-label con long-tail (Ben-Baruch et al., 2021).

    - γ- > γ+: los negativos fáciles (alta confianza de que no está el código)
      se down-weightean agresivamente, liberando capacidad de gradiente para
      los positivos raros.
    - clip (probability margin): desplaza la probabilidad negativa en +clip antes
      de calcular el log, lo que elimina el ruido de negativos "casi positivos"
      (umbrales de anotación, sinónimos parciales).

    Parámetros recomendados (paper, datasets multi-label con long-tail):
      γ+=0, γ-=4, clip=0.05  — agresivo en negativos, neutral en positivos
      γ+=1, γ-=4, clip=0.05  — también penaliza positivos fáciles (ligeramente)
    """

    def __init__(
        self,
        gamma_neg: float = 4.0,
        gamma_pos: float = 1.0,
        clip: float = 0.05,
        eps: float = 1e-8,
    ):
        super().__init__()
        self.gamma_neg = gamma_neg
        self.gamma_pos = gamma_pos
        self.clip = clip
        self.eps = eps

    def forward(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        xs_pos = torch.sigmoid(x)
        xs_neg = 1.0 - xs_pos

        # Probability margin: desplaza negativos para ignorar los casi-positivos
        if self.clip > 0:
            xs_neg = (xs_neg + self.clip).clamp(max=1.0)

        lo_pos = y * torch.log(xs_pos.clamp(min=self.eps))
        lo_neg = (1 - y) * torch.log(xs_neg.clamp(min=self.eps))

        # Focusing: (1-pt)^γ — cuando el modelo es confiado, el peso → 0
        if self.gamma_neg > 0 or self.gamma_pos > 0:
            pt = xs_pos * y + xs_neg * (1 - y)  # p_t por clase y muestra
            gamma = self.gamma_pos * y + self.gamma_neg * (1 - y)
            w = torch.pow(1.0 - pt, gamma)
            lo_pos = lo_pos * w
            lo_neg = lo_neg * w

        return -(lo_pos + lo_neg).mean()


def zlpr_loss(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    """Pérdida listwise dentro del documento (ZLPR).

        L = log(1 + Σ_{j∈neg} e^{z_j}) + log(1 + Σ_{i∈pos} e^{−z_i})

    La BCE trata cada código como un problema independiente: optimiza que la
    probabilidad de cada clase esté bien calibrada, no que los códigos correctos de un
    informe queden por encima de los incorrectos DE ESE MISMO informe. El MAP mide
    exactamente eso último, así que la métrica y la pérdida están desalineadas. Esta
    pérdida cierra esa brecha: es mínima cuando todos los positivos del documento
    superan a todos sus negativos, sin exigir ningún valor absoluto concreto.

    Se calcula en float32: el logsumexp recorre 1767 términos y bf16 pierde precisión.
    """
    z = logits.float()
    t = targets.float()
    neg = z.masked_fill(t >= 0.5, -1e9)  # solo negativos
    pos = (-z).masked_fill(t < 0.5, -1e9)  # solo positivos, con el signo cambiado
    zero = torch.zeros_like(z[..., :1])  # el "1 +" del logaritmo
    neg_term = torch.logsumexp(torch.cat([neg, zero], dim=-1), dim=-1)
    pos_term = torch.logsumexp(torch.cat([pos, zero], dim=-1), dim=-1)
    return (neg_term + pos_term).mean()


def rdrop_loss(logits_a: torch.Tensor, logits_b: torch.Tensor) -> torch.Tensor:
    """Divergencia KL simétrica entre dos pasadas con máscaras de dropout distintas.

    R-Drop penaliza que el modelo conteste cosas distintas al mismo informe según qué
    neuronas se apaguen. Es regularización que no usa las etiquetas, de modo que aprovecha
    los 500 documentos sin depender de cuántos positivos tenga cada código — el punto débil
    de este corpus. Cada clase es una Bernoulli independiente, así que la divergencia se
    promedia sobre las clases para quedar en la misma escala que la BCE.
    """
    eps = 1e-6
    pa = torch.sigmoid(logits_a.float()).clamp(eps, 1 - eps)
    pb = torch.sigmoid(logits_b.float()).clamp(eps, 1 - eps)
    kl_ab = pa * (pa.log() - pb.log()) + (1 - pa) * ((1 - pa).log() - (1 - pb).log())
    kl_ba = pb * (pb.log() - pa.log()) + (1 - pb) * ((1 - pb).log() - (1 - pa).log())
    return 0.5 * (kl_ab + kl_ba).mean()


class WeightEMA:
    """Media móvil exponencial de los pesos entrenables.

    Promediar las salidas de varias ejecuciones sube el MAP, pero multiplica el coste de
    inferencia y por eso no cabe en el VPS. La EMA persigue el mismo efecto —reducir la
    varianza de los pesos— dentro de UNA sola trayectoria: los puntos que promedia están
    en la misma cuenca por construcción y el resultado sigue siendo un único modelo.

    Solo se siguen los parámetros entrenables: los congelados no cambian, así que su media
    sería ellos mismos. Los que aparecen con el descongelado progresivo se incorporan al
    vuelo, con su valor del momento como punto de partida.
    """

    def __init__(self, model: nn.Module, decay: float):
        self.decay = decay
        self.shadow = {
            n: p.detach().clone().float() for n, p in model.named_parameters() if p.requires_grad
        }

    @torch.no_grad()
    def update(self, model: nn.Module):
        for n, p in model.named_parameters():
            if not p.requires_grad:
                continue
            if n in self.shadow:
                self.shadow[n].mul_(self.decay).add_(p.detach().float(), alpha=1.0 - self.decay)
            else:
                self.shadow[n] = p.detach().clone().float()

    @contextmanager
    def applied(self, model: nn.Module):
        """Sustituye temporalmente los pesos del modelo por los de la media móvil."""
        backup = {}
        with torch.no_grad():
            for n, p in model.named_parameters():
                if n in self.shadow:
                    backup[n] = p.detach().clone()
                    p.copy_(self.shadow[n].to(p.dtype))
        try:
            yield
        finally:
            with torch.no_grad():
                for n, p in model.named_parameters():
                    if n in backup:
                        p.copy_(backup[n])


def compute_pos_weight(train_loader, num_labels: int, device, cap: float = 50.0):
    """
    Calcula pos_weight por clase = (#negativos) / (#positivos) para BCEWithLogitsLoss.
    Con cap evitamos pesos extremos en códigos rarísimos.
    """
    pos_counts = torch.zeros(num_labels)
    total = 0
    for batch in train_loader:
        pos_counts += batch["labels"].sum(dim=0)
        total += batch["labels"].shape[0]
    neg_counts = total - pos_counts
    weight = (neg_counts / pos_counts.clamp(min=1)).clamp(max=cap)
    print(f"[loss] pos_weight media={weight.mean():.1f}  max={weight.max():.1f}  (cap={cap})")
    return weight.to(device)


def build_hier_pairs(code_to_idx):
    """Para cada código de ≥4 chars, busca su padre de 3 chars en el label set.
    Devuelve (child_indices, parent_indices) como listas de enteros, o None si no hay pares."""
    child_ids, parent_ids = [], []
    for code, idx in code_to_idx.items():
        if len(code) > 3:
            parent = code[:3]
            if parent in code_to_idx:
                child_ids.append(idx)
                parent_ids.append(code_to_idx[parent])
    if not child_ids:
        return None
    print(f"[hier] {len(child_ids)} child→parent pairs found in label set")
    return torch.tensor(child_ids, dtype=torch.long), torch.tensor(parent_ids, dtype=torch.long)


def train(
    model,
    train_loader,
    val_loader,
    device,
    epochs,
    patience,
    grad_accum,
    pos_weight_cap=10.0,
    threshold=0.5,
    lr=5e-6,
    weight_decay=0.01,
    warmup_ratio=0.1,
    asl_gamma_neg=0.0,
    asl_gamma_pos=0.0,
    asl_clip=0.05,
    label_smoothing=0.0,
    lr_schedule="cosine",
    unfreeze_every=0,
    unfreeze_layers=4,
    unfreeze_lr_ratio=0.1,
    lambda_hier=0.0,
    hier_pairs=None,
    select_metric="f1_micro",
    distill_alpha=0.5,
    rank_loss_weight=0.0,
    rdrop_alpha=0.0,
    ema_decay=0.0,
):
    # Solo parámetros con requires_grad=True: los congelados quedan fuera del optimizer
    # para poder añadirlos como nuevo param group al descongelarlos (add_param_group)
    # sin que PyTorch los detecte como duplicados.
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=lr,
        weight_decay=weight_decay,
    )

    # Scheduler
    if lr_schedule == "plateau":
        # ReduceLROnPlateau: baja el LR cuando la métrica de selección no mejora durante
        # patience//2 épocas.
        # Más adaptativo que cosine: no decae a 0 arbitrariamente sino solo cuando hay estancamiento.
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="max", factor=0.5, patience=max(1, patience // 2)
        )
        print(f"[scheduler] ReduceLROnPlateau  factor=0.5  patience={max(1, patience // 2)}")
    else:
        # Cosine con warmup (default): warmup lineal + decaída coseno hasta 0
        total_opt_steps = (len(train_loader) // grad_accum) * epochs
        warmup_steps = max(1, int(warmup_ratio * total_opt_steps))
        scheduler = get_cosine_schedule_with_warmup(
            optimizer,
            num_warmup_steps=warmup_steps,
            num_training_steps=total_opt_steps,
        )
        print(f"[scheduler] cosine  warmup={warmup_steps} steps  total={total_opt_steps} steps")
    if asl_gamma_neg > 0 or asl_gamma_pos > 0:
        loss_fn = AsymmetricLoss(gamma_neg=asl_gamma_neg, gamma_pos=asl_gamma_pos, clip=asl_clip)
        print(f"[loss] AsymmetricLoss  γ-={asl_gamma_neg}  γ+={asl_gamma_pos}  clip={asl_clip}")
    else:
        pos_weight = compute_pos_weight(
            train_loader, model.classifier.out_features, device, cap=pos_weight_cap
        )
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        print(f"[loss] BCEWithLogitsLoss  pos_weight_cap={pos_weight_cap}")
    autocast = _autocast_ctx(device)

    # Hierarchical consistency loss tensors → mover al device una sola vez
    if hier_pairs is not None and lambda_hier > 0.0:
        hier_child = hier_pairs[0].to(device)
        hier_parent = hier_pairs[1].to(device)
        print(f"[hier] lambda_hier={lambda_hier}  pairs={len(hier_child)}")
    else:
        hier_child = hier_parent = None

    ema = WeightEMA(model, ema_decay) if ema_decay > 0.0 else None
    if ema is not None:
        print(f"[ema] media móvil de pesos  decay={ema_decay}  (se evalúa y guarda la EMA)")
    if rank_loss_weight > 0.0:
        print(f"[loss] + ZLPR listwise por documento  peso={rank_loss_weight}")
    if rdrop_alpha > 0.0:
        print(f"[loss] + R-Drop  alpha={rdrop_alpha}  (dos pasadas por batch)")

    best_score = -1.0
    best_state = None
    no_improve = 0
    history = []  # [{epoch, train_loss, val_f1_micro, val_f1_macro}]
    epoch_times = []  # segundos por época para ETA

    n_batches = len(train_loader)
    print(f"\n{'=' * 60}")
    print(f"  epochs={epochs}  patience={patience}  grad_accum={grad_accum}")
    print(f"  select_metric={select_metric}  (checkpoint y scheduler)")
    if getattr(train_loader.dataset, "teacher_probs", None) is not None:
        print(f"  destilación activa  alpha={distill_alpha}  (peso de las etiquetas duras)")
    print(f"  batches/epoch={n_batches}  opt_steps/epoch={n_batches // grad_accum}")
    print(f"{'=' * 60}")

    def fmt_seconds(s):
        s = int(s)
        h, m = divmod(s, 3600)
        m, s = divmod(m, 60)
        return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"

    def _eval_and_snapshot(current_best):
        """Evalúa en validación y, si mejora, devuelve una copia de los pesos actuales."""
        m = evaluate(model, val_loader, device, threshold=threshold)
        state = None
        if m[select_metric] > current_best:
            state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        return m, state

    train_start = time.time()

    # El descongelado progresivo añade parámetros (y sus momentos de Adam) en mitad del
    # entrenamiento, así que el pico de memoria no llega al principio sino a la época 30,
    # 60, 90... Si la GPU se agota ahí, se conserva el mejor checkpoint alcanzado en vez de
    # perder la ejecución entera: los artefactos se escriben igual con lo que haya.
    try:
        for epoch in range(1, epochs + 1):
            model.train()
            epoch_loss = 0.0
            epoch_start = time.time()
            step_times = []
            optimizer.zero_grad()

            for step, batch in enumerate(train_loader):
                step_start = time.time()
                with autocast:
                    logits = model(
                        batch["input_ids"].to(device),
                        batch["attention_mask"].to(device),
                        doc_chunk_counts=batch.get("doc_chunk_counts"),
                    )
                    labels = batch["labels"].to(device)
                    if label_smoothing > 0.0:
                        # One-sided label smoothing: solo suaviza los positivos (1 → 1-ε).
                        # Los negativos se mantienen en 0. Así no interactúa con pos_weight:
                        # si se suavizara también el 0 → ε/2, pos_weight amplificaría ese
                        # gradiente espúreo sobre 497 negativos por código, aplastando la señal
                        # real y haciendo que el modelo prediga todo como positivo.
                        labels = labels * (1.0 - label_smoothing)
                    bce_loss = loss_fn(logits, labels)
                    extra = {}
                    if rdrop_alpha > 0.0:
                        # Segunda pasada sobre el MISMO batch: mismo texto, otra máscara de
                        # dropout. La diferencia entre ambas salidas es lo que se penaliza.
                        logits_b = model(
                            batch["input_ids"].to(device),
                            batch["attention_mask"].to(device),
                            doc_chunk_counts=batch.get("doc_chunk_counts"),
                        )
                        bce_loss = 0.5 * (bce_loss + loss_fn(logits_b, labels))
                        extra["rdrop"] = rdrop_alpha * rdrop_loss(logits, logits_b)
                    if rank_loss_weight > 0.0:
                        extra["zlpr"] = rank_loss_weight * zlpr_loss(logits, labels)
                    if "teacher" in batch:
                        # Destilación: además de las etiquetas binarias, imitar las
                        # probabilidades del profesor. Sin pos_weight — los objetivos blandos
                        # ya llevan la información de ordenación que interesa al MAP.
                        soft_loss = nn.functional.binary_cross_entropy_with_logits(
                            logits, batch["teacher"].to(device)
                        )
                        bce_loss = distill_alpha * bce_loss + (1.0 - distill_alpha) * soft_loss
                    total = bce_loss + sum(extra.values())
                    if hier_child is not None:
                        # Penalizar cuando logit_hijo > logit_padre: relu(child - parent).
                        # Asimétrico: no penaliza si padre > hijo (consistente). No modifica la
                        # arquitectura — solo presiona al modelo a activar el padre cuando activa el hijo.
                        hier_loss = torch.relu(
                            logits[:, hier_child] - logits[:, hier_parent]
                        ).mean()
                        total = total + lambda_hier * hier_loss
                    loss = total / grad_accum
                loss.backward()
                epoch_loss += loss.item() * grad_accum

                if step % grad_accum == 0 or step == len(train_loader):
                    nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                    optimizer.step()
                    if lr_schedule == "cosine":
                        scheduler.step()
                    optimizer.zero_grad()
                    if ema is not None:
                        ema.update(model)

                step_times.append(time.time() - step_start)

                log_every = max(1, n_batches // 4)
                if step % log_every == 0:
                    avg_step = sum(step_times) / len(step_times)
                    remaining = avg_step * (n_batches - step)
                    detail = "".join(f"  {k}={v.item():.4f}" for k, v in extra.items())
                    print(
                        f"  epoch {epoch}/{epochs}  step {step}/{n_batches}"
                        f"  loss={loss.item() * grad_accum:.4f}"
                        f"  bce={bce_loss.item():.4f}{detail}"
                        f"  {avg_step:.1f}s/step  epoch ETA {fmt_seconds(remaining)}"
                    )

            epoch_elapsed = time.time() - epoch_start
            epoch_times.append(epoch_elapsed)

            avg_loss = epoch_loss / n_batches
            # Con EMA activa se evalúa —y se guarda— la media móvil, no los pesos del último
            # paso: es la media la que se quiere llevar a producción.
            if ema is not None:
                with ema.applied(model):
                    m, snapshot = _eval_and_snapshot(best_score)
            else:
                m, snapshot = _eval_and_snapshot(best_score)
            history.append(
                {
                    "epoch": epoch,
                    "train_loss": avg_loss,
                    **{f"val_{k}": v for k, v in m.items()},
                    "epoch_seconds": round(epoch_elapsed, 1),
                }
            )

            avg_epoch_time = sum(epoch_times) / len(epoch_times)
            epochs_left = epochs - epoch
            total_eta = avg_epoch_time * epochs_left
            elapsed_total = time.time() - train_start

            current_lr = optimizer.param_groups[0]["lr"]
            print(
                f"  epoch {epoch}/{epochs}  loss={avg_loss:.4f}  lr={current_lr:.2e}"
                f"  P={m['p_micro']:.3f}  R={m['r_micro']:.3f}  F1={m['f1_micro']:.3f} (micro)"
                f"  |  P={m['p_macro']:.3f}  R={m['r_macro']:.3f}  F1={m['f1_macro']:.3f} (macro)"
                f"  |  MAP={m['map_macro']:.3f}"
                f"  [{fmt_seconds(epoch_elapsed)}/epoch  elapsed {fmt_seconds(elapsed_total)}"
                f"  ETA {fmt_seconds(total_eta)}]"
            )

            if lr_schedule == "plateau":
                scheduler.step(m[select_metric])

            if snapshot is not None:
                best_score = m[select_metric]
                best_state = snapshot
                no_improve = 0
                print(f"  → new best {select_metric}: {best_score:.4f}  (saved)")
            else:
                no_improve += 1
                print(f"  → no improvement ({no_improve}/{patience})")
                if no_improve >= patience:
                    print("  Early stopping.")
                    break

            # Progressive unfreezing: cada unfreeze_every épocas, activar el siguiente bloque
            # de capas con LR reducido. Resetear no_improve para dar margen al modelo tras
            # descongelar nuevos parámetros.
            if unfreeze_every > 0 and epoch % unfreeze_every == 0:
                new_params = model.unfreeze_next_group(unfreeze_layers)
                if new_params:
                    new_lr = lr * unfreeze_lr_ratio
                    optimizer.add_param_group(
                        {
                            "params": new_params,
                            "lr": new_lr,
                            "weight_decay": weight_decay,
                        }
                    )
                    no_improve = 0
                    print(
                        f"  [unfreeze] nuevo param group  lr={new_lr:.2e}  (early stopping reseteado)"
                    )
    except torch.OutOfMemoryError as exc:
        print(f"\n  [abort] memoria de GPU agotada en la época {epoch}: {exc}")
        print(f"  Se conserva el mejor {select_metric} alcanzado: {best_score:.4f}")
        torch.cuda.empty_cache()
    except KeyboardInterrupt:
        print(
            f"\n  [abort] interrumpido en la época {epoch}. Mejor {select_metric}: {best_score:.4f}"
        )

    print(f"\n  Best val {select_metric}: {best_score:.4f}")
    return best_state or model.state_dict(), history


# ==================== MAIN ====================


def main():
    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir / "../training/csv_import_scripts"

    parser = argparse.ArgumentParser(description="Train flat CIE-10 classifier (RigoBERTa)")
    parser.add_argument(
        "--train_file",
        default=str(data_dir / "codiesp_csvs/codiesp_D_source_train.csv"),
    )
    parser.add_argument(
        "--val_file",
        default=str(data_dir / "codiesp_csvs/codiesp_D_source_validation.csv"),
    )
    parser.add_argument("--cie10_file", default=str(data_dir / "cie10-csvs/cie10-es-diagnoses.csv"))
    parser.add_argument("--output_dir", default=str(script_dir / "model"))
    parser.add_argument("--model_name", default="IIC/RigoBERTa-Clinical")
    parser.add_argument("--max_length", type=int, default=1024)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument(
        "--grad_accum",
        type=int,
        default=4,
        help="Gradient accumulation steps (virtual batch = batch_size * grad_accum)",
    )
    parser.add_argument("--threshold", type=float, default=0.2)
    parser.add_argument("--device", default="auto")
    parser.add_argument(
        "--full_codes",
        action="store_true",
        help="Usar código completo (B86.93D). Por defecto: solo bloque (B86)",
    )
    parser.add_argument(
        "--chapters",
        action="store_true",
        help="Clasificar por capítulo CIE-10 (~20 clases) en vez de por bloque (809 clases). "
        "Útil como sanity-check: con 20 clases se espera F1>0.70.",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=5e-6,
        help="Learning rate para AdamW (default: 5e-6)",
    )
    parser.add_argument(
        "--pos_weight_cap",
        type=float,
        default=10.0,
        help="Cap máximo para pos_weight por clase (default: 10.0). "
        "Valores altos (>=50) sobrepenalizan falsos negativos y producen recall alto pero precision baja. "
        "Ignorado si --asl_gamma_neg > 0.",
    )
    parser.add_argument(
        "--asl_gamma_neg",
        type=float,
        default=0.0,
        help="Asymmetric Loss: γ- para ejemplos negativos (default: 0 = BCE normal). "
        "Valor típico: 4.0. Down-weightea negativos fáciles para centrarse en positivos raros.",
    )
    parser.add_argument(
        "--asl_gamma_pos",
        type=float,
        default=0.0,
        help="Asymmetric Loss: γ+ para ejemplos positivos (default: 0). "
        "Valor típico: 0.0 o 1.0. Con 0, los positivos no tienen focusing extra.",
    )
    parser.add_argument(
        "--asl_clip",
        type=float,
        default=0.05,
        help="Asymmetric Loss: probability margin para negativos (default: 0.05). "
        "Desplaza la probabilidad negativa para ignorar falsos negativos débiles.",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=5,
        help="Paciencia para early stopping (default: 5). Detiene si no hay mejora en F1-micro tras N épocas.",
    )
    parser.add_argument(
        "--dropout",
        type=float,
        default=0.1,
        help="Dropout en la cabeza clasificadora (default: 0.1)",
    )
    parser.add_argument(
        "--freeze_layers",
        type=int,
        default=0,
        help="Número de capas del encoder a congelar desde abajo (default: 0 = ninguna). "
        "Ej: 20 congela las 20 primeras capas de 24, dejando solo las 4 últimas + cabeza entrenable.",
    )
    parser.add_argument(
        "--warmup_ratio",
        type=float,
        default=0.1,
        help="Fracción de pasos totales usados para warmup del LR (default: 0.1).",
    )
    parser.add_argument(
        "--weight_decay",
        type=float,
        default=0.01,
        help="Weight decay para AdamW (default: 0.01).",
    )
    parser.add_argument(
        "--sliding_window",
        action="store_true",
        help="Codificar el texto completo como ventanas solapadas de max_length tokens y "
        "hacer mean-pool de los embeddings [CLS] por documento. "
        "Sin este flag se trunca al primer max_length tokens.",
    )
    parser.add_argument(
        "--chunk_overlap",
        type=int,
        default=64,
        help="Stride en tokens entre ventanas consecutivas cuando --sliding_window está activo "
        "(default: 64). Menor overlap = menos redundancia y más velocidad.",
    )
    parser.add_argument(
        "--pretrain_epochs",
        type=int,
        default=0,
        help="Épocas de pre-entrenamiento sobre las descripciones del diccionario CIE-10 antes "
        "del fine-tuning en CodiESP (default: 0 = sin pre-entrenamiento). Cada descripción "
        "del CSV (y sus variantes separadas por '|') se usa como muestra de entrenamiento.",
    )
    parser.add_argument(
        "--pretrain_taskx",
        nargs="*",
        default=None,
        help="Rutas a ficheros CSV de task_X (codiesp_X_source_*.csv) para añadir snippets "
        "clínicos reales (anotaciones DIAGNOSTICO) al pre-entrenamiento. "
        "Ej: --pretrain_taskx /data/codiesp_csvs/codiesp_X_source_train.csv "
        "/data/codiesp_csvs/codiesp_X_source_validation.csv",
    )
    parser.add_argument(
        "--label_smoothing",
        type=float,
        default=0.0,
        help="Label smoothing binario (default: 0 = off). Con ε>0: target 1 → 1-ε/2, target 0 → ε/2. "
        "Regulariza la loss evitando predicciones sobreconfiadas. Valores típicos: 0.05–0.15.",
    )
    parser.add_argument(
        "--lr_schedule",
        choices=["cosine", "plateau"],
        default="cosine",
        help="Scheduler de LR (default: cosine). "
        "'cosine': warmup lineal + decaída coseno hasta 0 en max_epochs. "
        "'plateau': ReduceLROnPlateau, baja LR×0.5 cuando F1-micro no mejora patience//2 épocas.",
    )
    parser.add_argument(
        "--unfreeze_every",
        type=int,
        default=0,
        help="Progressive unfreezing: descongelar --unfreeze_layers capas cada N épocas "
        "(0 = desactivado). Requiere --freeze_layers > 0. La cabeza se estabiliza "
        "las primeras N épocas con solo 4 capas libres; luego se van activando las "
        "capas superiores con LR reducido (--unfreeze_lr_ratio).",
    )
    parser.add_argument(
        "--unfreeze_layers",
        type=int,
        default=4,
        help="Capas a descongelar en cada paso de progressive unfreezing (default: 4).",
    )
    parser.add_argument(
        "--unfreeze_lr_ratio",
        type=float,
        default=0.1,
        help="Fracción del LR base para las capas recién descongeladas (default: 0.1). "
        "Ej: lr=1e-4, ratio=0.1 → nuevo param group a LR=1e-5.",
    )
    parser.add_argument(
        "--lambda_hier",
        type=float,
        default=0.0,
        help="Peso del regularizador jerárquico CIE-10 (default: 0 = desactivado). "
        "Penaliza cuando logit_hijo > logit_padre para pares (código 4+chars, padre 3chars) "
        "que existan en el label set. Valores típicos: 0.1–1.0.",
    )
    parser.add_argument(
        "--push_to_hub",
        action="store_true",
        help="Publicar el checkpoint en Hugging Face si mejora el mejor F1 o el mejor MAP "
        "registrado en training_runs.csv (default: no publicar, solo informar).",
    )
    parser.add_argument(
        "--hf_repo",
        default="dmartingarcia/cie10-rigoberta-classifier",
        help="Repo de Hugging Face destino de --push_to_hub.",
    )
    parser.add_argument(
        "--distill_from",
        nargs="*",
        default=None,
        help="Rutas a checkpoints .pt cuyo promedio de probabilidades actúa como profesor. "
        "El alumno entrena contra ese promedio además de contra las etiquetas del corpus, "
        "con coste de inferencia de un solo modelo.",
    )
    parser.add_argument(
        "--distill_alpha",
        type=float,
        default=0.5,
        help="Peso de las etiquetas duras frente al profesor (default: 0.5). "
        "1.0 = solo etiquetas (sin destilación); 0.0 = solo profesor.",
    )
    parser.add_argument(
        "--select_metric",
        default="f1_micro",
        choices=["f1_micro", "f1_macro", "map_macro"],
        help="Métrica de validación que decide el mejor checkpoint y guía al scheduler "
        "plateau (default: f1_micro). map_macro optimiza directamente el MAP de CodiEsp, "
        "que es independiente del umbral.",
    )
    parser.add_argument(
        "--rank_loss_weight",
        type=float,
        default=0.0,
        help="Peso del término ZLPR listwise por documento, que optimiza directamente la "
        "ordenación que mide el MAP (default: 0 = desactivado). Se SUMA a la BCE; con la "
        "BCE ya convergida en torno a 0.03, un peso de 0.1 deja ambos términos en la misma "
        "escala.",
    )
    parser.add_argument(
        "--rdrop_alpha",
        type=float,
        default=0.0,
        help="Peso de la divergencia KL simétrica entre dos pasadas con dropout distinto "
        "(R-Drop). Duplica el coste por batch. Default: 0 = desactivado.",
    )
    parser.add_argument(
        "--ema_decay",
        type=float,
        default=0.0,
        help="Decaimiento de la media móvil exponencial de los pesos (p. ej. 0.999). Se "
        "evalúa y se guarda la media, no el último paso. Default: 0 = desactivado.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Semilla para torch/numpy/random. Sin ella cada ejecución es un sorteo "
        "independiente, que es lo que permite medir el ruido estocástico.",
    )
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)
        torch.manual_seed(args.seed)
        torch.cuda.manual_seed_all(args.seed)
        print(f"[seed] {args.seed}")

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
    codes, code_to_idx, idx_to_code = build_encoders(
        train_df, full_codes=args.full_codes, chapters=args.chapters
    )

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
    print("\n[model] Loading tokenizer …")
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)

    # Datasets
    if args.sliding_window:
        print(f"[data] sliding_window=True  chunk_overlap={args.chunk_overlap} tokens")

    def make_loader(df, shuffle, teacher_probs=None):
        ds = CIE10Dataset(
            df["text"].tolist(),
            df["labels"].tolist(),
            tokenizer,
            args.max_length,
            code_to_idx,
            full_codes=args.full_codes,
            chapters=args.chapters,
            sliding_window=args.sliding_window,
            chunk_overlap=args.chunk_overlap,
            teacher_probs=teacher_probs,
        )
        collate = sliding_window_collate if args.sliding_window else None
        return DataLoader(
            ds,
            batch_size=args.batch_size,
            shuffle=shuffle,
            num_workers=2,
            collate_fn=collate,
        )

    teacher_probs = None
    if args.distill_from:
        if args.sliding_window:
            raise SystemExit("--distill_from no es compatible con --sliding_window")
        print(f"\n[distill] calculando profesor a partir de {len(args.distill_from)} checkpoints")
        teacher_probs = compute_teacher_probs(
            args.distill_from,
            train_df["text"].astype(str).tolist(),
            tokenizer,
            args.model_name,
            args.max_length,
            args.batch_size,
            device,
            code_to_idx,
        )

    train_loader = make_loader(train_df, shuffle=True, teacher_probs=teacher_probs)
    val_loader = make_loader(val_df, shuffle=False)

    # Model
    print(f"[model] Initialising FlatClassifier ({len(codes)} codes) …")
    model = FlatClassifier(
        args.model_name,
        num_codes=len(codes),
        dropout=args.dropout,
        freeze_layers=args.freeze_layers,
    ).to(device)
    ctx = _autocast_ctx(device)
    _dtype = getattr(ctx, "_dtype", "bfloat16")
    print(f"[model] mixed precision: {_dtype} autocast en {device.type}")

    # Pre-training sobre descripciones CIE-10 + snippets task_X (opcional)
    if args.pretrain_epochs > 0:
        pretrain_loader = build_pretrain_loader(
            args.cie10_file,
            tokenizer,
            args.max_length,
            code_to_idx,
            args.full_codes,
            args.batch_size,
            taskx_files=args.pretrain_taskx,
        )
        pretrain(
            model,
            pretrain_loader,
            device,
            epochs=args.pretrain_epochs,
            lr=args.lr,
            weight_decay=args.weight_decay,
        )

    # Hierarchical pairs: solo con full_codes (códigos 4+ chars → padre 3 chars)
    hier_pairs = build_hier_pairs(code_to_idx) if args.lambda_hier > 0.0 else None

    # Train
    best_state, history = train(
        model,
        train_loader,
        val_loader,
        device,
        epochs=args.epochs,
        patience=args.patience,
        grad_accum=args.grad_accum,
        pos_weight_cap=args.pos_weight_cap,
        threshold=args.threshold,
        lr=args.lr,
        weight_decay=args.weight_decay,
        warmup_ratio=args.warmup_ratio,
        asl_gamma_neg=args.asl_gamma_neg,
        asl_gamma_pos=args.asl_gamma_pos,
        asl_clip=args.asl_clip,
        label_smoothing=args.label_smoothing,
        lr_schedule=args.lr_schedule,
        unfreeze_every=args.unfreeze_every,
        unfreeze_layers=args.unfreeze_layers,
        unfreeze_lr_ratio=args.unfreeze_lr_ratio,
        lambda_hier=args.lambda_hier,
        hier_pairs=hier_pairs,
        select_metric=args.select_metric,
        distill_alpha=args.distill_alpha,
        rank_loss_weight=args.rank_loss_weight,
        rdrop_alpha=args.rdrop_alpha,
        ema_decay=args.ema_decay,
    )

    # Save
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[save] Writing artifacts → {output_dir.resolve()}")

    with open(output_dir / "cie10_chapters.json", "w", encoding="utf-8") as f:
        json.dump(CIE10_CHAPTERS, f, ensure_ascii=False, indent=2)
    print("[save] cie10_chapters.json")

    with open(output_dir / "code_descriptions.json", "w", encoding="utf-8") as f:
        json.dump(code_descriptions, f, ensure_ascii=False, indent=2)
    print("[save] code_descriptions.json")

    # Final eval con el mejor modelo
    model.load_state_dict(best_state)
    model.to(device)

    # Threshold sweep: global → por clase
    probs_val, targets_val = _collect_probs(model, val_loader, device)

    # 1) Global: threshold único que maximiza F1-micro
    best_global_thr, best_global_f1 = 0.5, -1.0
    for thr in np.linspace(0.05, 0.95, 19):
        P = (probs_val >= thr).astype(int)
        f1 = float(f1_score(targets_val, P, average="micro", zero_division=0))
        if f1 > best_global_f1:
            best_global_f1, best_global_thr = f1, float(thr)
    best_global_thr = round(best_global_thr, 4)
    print(
        f"\n[threshold] global → óptimo={best_global_thr:.2f}  F1-micro={best_global_f1:.4f}  "
        f"(configurado={args.threshold})"
    )

    # 2) Por clase: threshold individual para maximizar F1 binario de cada código
    per_class_thr = find_optimal_thresholds_per_class(
        probs_val, targets_val, global_thr=best_global_thr
    )
    P_per_class = (probs_val >= per_class_thr).astype(int)
    f1_per_class_micro = float(f1_score(targets_val, P_per_class, average="micro", zero_division=0))
    f1_per_class_macro = float(f1_score(targets_val, P_per_class, average="macro", zero_division=0))
    print(
        f"[threshold] por clase → F1-micro={f1_per_class_micro:.4f}  F1-macro={f1_per_class_macro:.4f}"
    )

    # MAP macro sobre clases con positivos en validación (no comparable directamente
    # con el MAP por documento de CodiEsp, que promedia sobre documentos, no clases).
    map_macro = _map_codiesp(targets_val, probs_val)
    print(f"[threshold] MAP macro={map_macro:.4f}  (benchmark CodiEsp best≈0.48)")

    # Usar global para eval final (el per-class se guarda como artefacto opcional)
    final_thr = best_global_thr
    fm = evaluate(model, val_loader, device, threshold=final_thr)
    print(f"\n[result] threshold={final_thr}")
    print(f"  micro — P={fm['p_micro']:.4f}  R={fm['r_micro']:.4f}  F1={fm['f1_micro']:.4f}")
    print(f"  macro — P={fm['p_macro']:.4f}  R={fm['r_macro']:.4f}  F1={fm['f1_macro']:.4f}")

    # ---- CSV de run ----
    import csv
    from datetime import datetime

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    # Guardar modelo con timestamp, F1 y MAP para no machacar versiones anteriores
    model_filename = f"classifier_{timestamp}_f1={fm['f1_micro']:.4f}_map={map_macro:.4f}.pt"
    torch.save(
        {
            "code_to_idx": code_to_idx,
            "idx_to_code": idx_to_code,
            "model_state_dict": best_state,
        },
        output_dir / model_filename,
    )
    print(f"[save] {model_filename}")

    # Guardar thresholds por clase (para inferencia avanzada)
    thr_path = output_dir / f"thresholds_{timestamp}.json"
    with open(thr_path, "w") as f:
        json.dump(
            {
                "global_threshold": final_thr,
                "per_class_thresholds": per_class_thr.tolist(),
                "idx_to_code": idx_to_code,
                "f1_micro_global": round(best_global_f1, 6),
                "f1_micro_per_class": round(f1_per_class_micro, 6),
                "f1_macro_per_class": round(f1_per_class_macro, 6),
                "map_macro": round(map_macro, 6),
            },
            f,
            indent=2,
        )
    print(f"[save] {thr_path.name}  (thresholds por clase)")

    with open(output_dir / "config.json", "w") as f:
        json.dump(
            {
                "model_name": args.model_name,
                "model_file": model_filename,
                "thresholds_file": thr_path.name,
                "max_length": args.max_length,
                "threshold": final_thr,
                "threshold_configured": args.threshold,
                "full_codes": args.full_codes,
            },
            f,
            indent=2,
        )
    print("[save] config.json")
    runs_csv = output_dir / "training_runs.csv"
    prev_best = _previous_bests(runs_csv)  # antes de añadir la fila de este run
    row = {
        "timestamp": timestamp,
        "model_name": args.model_name,
        "attn_impl": model.attn_impl,
        "full_codes": args.full_codes,
        "max_length": args.max_length,
        "epochs_run": len(history),
        "epochs_max": args.epochs,
        "batch_size": args.batch_size,
        "grad_accum": args.grad_accum,
        "effective_batch": args.batch_size * args.grad_accum,
        "lr": args.lr,
        "warmup_ratio": args.warmup_ratio,
        "dropout": args.dropout,
        "freeze_layers": args.freeze_layers,
        "weight_decay": args.weight_decay,
        "patience": args.patience,
        "threshold": final_thr,
        "threshold_configured": args.threshold,
        "label_smoothing": args.label_smoothing,
        "lr_schedule": args.lr_schedule,
        "unfreeze_every": args.unfreeze_every,
        "unfreeze_layers": args.unfreeze_layers,
        "unfreeze_lr_ratio": args.unfreeze_lr_ratio,
        "pos_weight_cap": args.pos_weight_cap,
        "asl_gamma_neg": args.asl_gamma_neg,
        "asl_gamma_pos": args.asl_gamma_pos,
        "asl_clip": args.asl_clip,
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "num_codes": len(codes),
        "val_p_micro": round(fm["p_micro"], 6),
        "val_r_micro": round(fm["r_micro"], 6),
        "val_f1_micro": round(fm["f1_micro"], 6),
        "val_p_macro": round(fm["p_macro"], 6),
        "val_r_macro": round(fm["r_macro"], 6),
        "val_f1_macro": round(fm["f1_macro"], 6),
        "val_map_macro": round(fm["map_macro"], 6),
        "total_seconds": round(sum(h["epoch_seconds"] for h in history), 1),
        "avg_epoch_seconds": round(sum(h["epoch_seconds"] for h in history) / len(history), 1),
        "sliding_window": args.sliding_window,
        "chunk_overlap": args.chunk_overlap if args.sliding_window else "",
        "pretrain_epochs": args.pretrain_epochs,
        "lambda_hier": args.lambda_hier,
        "select_metric": args.select_metric,
        "rank_loss_weight": args.rank_loss_weight,
        "rdrop_alpha": args.rdrop_alpha,
        "ema_decay": args.ema_decay,
        "seed": args.seed if args.seed is not None else "",
    }
    fieldnames = list(row.keys())
    if runs_csv.exists():
        with open(runs_csv, newline="") as f:
            existing_reader = csv.DictReader(f)
            # Las cabeceras de ficheros antiguos pueden venir con padding de alineación
            # (" model_name"). Sin normalizar, al reescribir con la cabecera nueva las
            # claves no casan y DictWriter rellena TODAS las filas viejas con restval="",
            # borrando el histórico.
            existing_fields = [(k or "").strip() for k in (existing_reader.fieldnames or [])]
            old_rows = [
                {(k or "").strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()}
                for r in existing_reader
            ]
        new_fields = [k for k in fieldnames if k not in existing_fields]
        if new_fields:
            # Rewrite file with extended header; old rows get empty string for new cols
            with open(runs_csv, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for old_row in old_rows:
                    writer.writerow(old_row)
        with open(runs_csv, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writerow(row)
    else:
        with open(runs_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(row)
    print("[save] training_runs.csv  (append)")

    # ---- ¿Mejora el mejor run anterior? → candidato a publicar en Hugging Face ----
    better_f1 = prev_best["f1"] is None or fm["f1_micro"] > prev_best["f1"]
    better_map = prev_best["map"] is None or map_macro > prev_best["map"]
    print(
        "\n[hub] mejor anterior — "
        f"F1={prev_best['f1'] if prev_best['f1'] is not None else float('nan'):.4f}  "
        f"MAP={prev_best['map'] if prev_best['map'] is not None else float('nan'):.4f}"
    )
    print(
        f"[hub] este run       — F1={fm['f1_micro']:.4f}{'  (mejor)' if better_f1 else ''}  "
        f"MAP={map_macro:.4f}{'  (mejor)' if better_map else ''}"
    )
    if better_f1 or better_map:
        print(
            "[hub] supera al mejor anterior. Para publicarlo:\n"
            f"      make model-upload BEST_PT={model_filename} BEST_THR={thr_path.name}"
        )
        if args.push_to_hub:
            push_to_hub(output_dir, model_filename, thr_path.name, args.hf_repo)
        else:
            print("[hub] no se publica: falta --push_to_hub")
    else:
        print("[hub] no mejora ni F1 ni MAP → no se publica")

    # ---- Historial de épocas (para gráfico comparativo multi-run) ----
    history_path = output_dir / f"training_history_{timestamp}.json"
    with open(history_path, "w") as f:
        json.dump(
            {
                "timestamp": timestamp,
                "model_name": args.model_name,
                "attn_impl": model.attn_impl,
                "max_length": args.max_length,
                "batch_size": args.batch_size,
                "grad_accum": args.grad_accum,
                "lr": args.lr,
                "threshold": args.threshold,
                "sliding_window": args.sliding_window,
                "chunk_overlap": args.chunk_overlap if args.sliding_window else None,
                "history": history,
            },
            f,
            indent=2,
        )
    print(f"[save] {history_path.name}")

    # ---- Gráfica ----
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    epochs_x = [h["epoch"] for h in history]
    losses = [h["train_loss"] for h in history]
    p_micro = [h["val_p_micro"] for h in history]
    r_micro = [h["val_r_micro"] for h in history]
    f1_micro = [h["val_f1_micro"] for h in history]
    f1_macro = [h["val_f1_macro"] for h in history]

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 11), sharex=True)

    ax1.plot(epochs_x, losses, marker="o", color="steelblue", label="train loss")
    ax1.set_ylabel("Loss")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(epochs_x, p_micro, marker="^", color="royalblue", label="Precision (micro)")
    ax2.plot(epochs_x, r_micro, marker="v", color="tomato", label="Recall (micro)")
    ax2.plot(
        epochs_x,
        f1_micro,
        marker="o",
        color="seagreen",
        label="F1 (micro)",
        linewidth=2,
    )
    ax2.set_ylabel("micro")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    ax3.plot(epochs_x, f1_micro, marker="o", color="seagreen", label="F1-micro")
    ax3.plot(epochs_x, f1_macro, marker="s", color="darkorange", label="F1-macro")
    ax3.set_ylabel("F1 micro vs macro")
    ax3.set_xlabel("Epoch")
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    fig.suptitle(
        f"{args.model_name}  [{model.attn_impl}]  —  {timestamp}\n"
        f"max_length={args.max_length}  batch={args.batch_size}×{args.grad_accum}={args.batch_size * args.grad_accum}"
        f"  lr={args.lr:.0e}  wd={args.weight_decay}  warmup={args.warmup_ratio}  dropout={args.dropout}"
        f"  threshold={args.threshold}  pos_weight_cap={args.pos_weight_cap}"
        f"  full_codes={args.full_codes}  epochs={len(history)}/{args.epochs}\n"
        f"F1-micro={fm['f1_micro']:.4f}  P={fm['p_micro']:.4f}  R={fm['r_micro']:.4f}"
        f"  |  F1-macro={fm['f1_macro']:.4f}"
    )
    plt.tight_layout()
    plot_path = output_dir / f"training_curve_{timestamp}.png"
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    print(f"[save] {plot_path.name}")

    print("[done]")


if __name__ == "__main__":
    main()
