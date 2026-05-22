"""
augment.py — Back-translation data augmentation (NLLB-200 local o Azure Translator).

Genera paráfrasis de cada nota clínica traduciendo ES→pivot→ES.
Las etiquetas CIE-10 se mantienen intactas.

Características:
  - NLLB-200: sin API, sin tarjeta, corre en la RTX 4080.
  - Azure Translator: free tier F0 = 2M chars/mes, sin tarjeta.
  - Checkpoint incremental: reanuda desde la última nota procesada.
  - Split por párrafos para notas que superan el límite de tokens de NLLB.

Uso:
    python augment.py                              # NLLB, EN pivot
    python augment.py --backend azure              # Azure Translator (lee AZURE_TRANSLATOR_KEY del env)
    python augment.py --pivot_langs EN FR          # dos pivots
    python augment.py --dry_run                    # solo muestra el estimado, sin traducir
    python augment.py --resume                     # retoma desde el checkpoint
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

NLLB_MODEL_DEFAULT = "facebook/nllb-200-distilled-1.3B"
NLLB_MAX_TOKENS    = 450   # margen bajo el límite real de 512

NLLB_LANG_CODES = {
    "EN": ("spa_Latn", "eng_Latn"),
    "FR": ("spa_Latn", "fra_Latn"),
    "DE": ("spa_Latn", "deu_Latn"),
}

AZURE_LANG_CODES = {
    "EN": ("es", "en"),
    "FR": ("es", "fr"),
    "DE": ("es", "de"),
}

AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com/translate"
AZURE_BATCH    = 100   # max items per request


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------

class NLLBTranslator:
    def __init__(self, model_name: str, batch_size: int):
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype  = torch.float16 if device == "cuda" else torch.float32
        print(f"[nllb] cargando {model_name} en {device}…")

        self.tokenizer  = AutoTokenizer.from_pretrained(model_name)
        self.model      = AutoModelForSeq2SeqLM.from_pretrained(
            model_name, torch_dtype=dtype
        ).to(device)
        self.model.eval()
        self.device     = device
        self.batch_size = batch_size
        print("[nllb] listo")

    def translate(self, texts: list[str], src_lang: str, tgt_lang: str) -> list[str]:
        import torch
        tgt_id = self.tokenizer.lang_code_to_id[tgt_lang]
        results = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            self.tokenizer.src_lang = src_lang
            enc = self.tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=NLLB_MAX_TOKENS,
            ).to(self.device)
            with torch.no_grad():
                out = self.model.generate(
                    **enc,
                    forced_bos_token_id=tgt_id,
                    max_new_tokens=NLLB_MAX_TOKENS,
                    num_beams=4,
                )
            results.extend(self.tokenizer.batch_decode(out, skip_special_tokens=True))
        return results


class AzureTranslator:
    def __init__(self, key: str, region: str):
        import requests  # stdlib-like, always available

        if not key:
            raise ValueError(
                "Azure Translator key vacío. "
                "Exporta AZURE_TRANSLATOR_KEY o usa --azure_key."
            )
        self._requests = requests
        self.key    = key
        self.region = region
        print(f"[azure] Translator listo (region: {region})")

    def translate(self, texts: list[str], src_lang: str, tgt_lang: str) -> list[str]:
        results = []
        for i in range(0, len(texts), AZURE_BATCH):
            batch = texts[i : i + AZURE_BATCH]
            body  = [{"text": t} for t in batch]
            resp  = self._requests.post(
                AZURE_ENDPOINT,
                params={
                    "api-version": "3.0",
                    "from": src_lang,
                    "to":   tgt_lang,
                },
                headers={
                    "Ocp-Apim-Subscription-Key":    self.key,
                    "Ocp-Apim-Subscription-Region": self.region,
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=60,
            )
            resp.raise_for_status()
            for item in resp.json():
                results.append(item["translations"][0]["text"])
        return results


# ---------------------------------------------------------------------------
# Back-translation
# ---------------------------------------------------------------------------

def _split_paragraphs(text: str, max_chars: int) -> list[str]:
    chunks, current = [], ""
    for para in (p for p in text.split("\n") if p.strip()):
        candidate = (current + "\n" + para).strip() if current else para
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = para[:max_chars]
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


def back_translate_nllb(translator: NLLBTranslator, text: str, pivot: str) -> str:
    src_code, tgt_code = NLLB_LANG_CODES[pivot]
    max_chars = NLLB_MAX_TOKENS * 4
    chunks = [text] if len(text) <= max_chars else _split_paragraphs(text, max_chars)
    fwd = translator.translate(chunks, src_lang=src_code, tgt_lang=tgt_code)
    bwd = translator.translate(fwd,    src_lang=tgt_code, tgt_lang=src_code)
    return "\n".join(bwd)


def back_translate_azure(translator: AzureTranslator, text: str, pivot: str) -> str:
    src_code, tgt_code = AZURE_LANG_CODES[pivot]
    fwd = translator.translate([text], src_lang=src_code, tgt_lang=tgt_code)
    bwd = translator.translate(fwd,   src_lang=tgt_code, tgt_lang=src_code)
    return bwd[0]


# ---------------------------------------------------------------------------
# CSV / checkpoint helpers
# ---------------------------------------------------------------------------

def _read_csv(path: str) -> tuple[list[str], list[dict]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return list(reader.fieldnames or []), rows


def _id_col(fieldnames: list[str]) -> str:
    for c in ("filename", "doc_id", "id", "file"):
        if c in fieldnames:
            return c
    return fieldnames[0]


def _write_csv(path: str, fieldnames: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _load_ckpt(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _save_ckpt(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend",      choices=["nllb", "azure"], default="nllb",
                        help="Backend de traducción (default: nllb)")
    # NLLB options
    parser.add_argument("--nllb_model",   default=NLLB_MODEL_DEFAULT,
                        help=f"Modelo NLLB (default: {NLLB_MODEL_DEFAULT})")
    parser.add_argument("--nllb_batch",   type=int, default=8)
    # Azure options
    parser.add_argument("--azure_key",    default=os.getenv("AZURE_TRANSLATOR_KEY", ""),
                        help="Azure Translator key (o exportar AZURE_TRANSLATOR_KEY)")
    parser.add_argument("--azure_region", default=os.getenv("AZURE_TRANSLATOR_REGION", "global"),
                        help="Región del recurso Azure (default: global)")
    # Data options
    parser.add_argument("--input_file",   default="/data/codiesp_csvs/codiesp_D_source_train.csv")
    parser.add_argument("--output_file",  default="/data/codiesp_csvs/codiesp_D_source_train_augmented.csv")
    parser.add_argument("--pivot_langs",  nargs="+", choices=list(NLLB_LANG_CODES), default=["EN"],
                        help="Lenguas de pivote (default: EN). Opciones: EN FR DE")
    parser.add_argument("--dry_run",      action="store_true",
                        help="Muestra estadísticas y sale sin traducir")
    parser.add_argument("--resume",       action="store_true",
                        help="Retoma desde el checkpoint existente")
    args = parser.parse_args()

    fieldnames, rows = _read_csv(args.input_file)
    id_col = _id_col(fieldnames)
    total_chars = sum(len(r.get("text", "")) for r in rows)

    print(f"[augment] backend: {args.backend} | {len(rows)} notas | {total_chars:,} chars | pivots: {args.pivot_langs}")
    print(f"[augment] augmentaciones: {len(rows) * len(args.pivot_langs)} notas nuevas "
          f"→ dataset total: {len(rows) * (1 + len(args.pivot_langs))} notas")

    if args.backend == "azure":
        azure_chars = total_chars * len(args.pivot_langs) * 2  # fwd + bwd
        print(f"[augment] Azure chars estimados: {azure_chars:,} "
              f"(free tier: 2,000,000/mes)")

    if args.dry_run:
        print("[augment] --dry_run: sin traducción. Saliendo.")
        return

    # Inicializar backend
    if args.backend == "nllb":
        translator   = NLLBTranslator(args.nllb_model, batch_size=args.nllb_batch)
        back_translate = lambda text, pivot: back_translate_nllb(translator, text, pivot)
    else:
        translator   = AzureTranslator(args.azure_key, args.azure_region)
        back_translate = lambda text, pivot: back_translate_azure(translator, text, pivot)

    ckpt_path  = Path(args.output_file).with_suffix(".ckpt.json")
    checkpoint = _load_ckpt(ckpt_path) if args.resume else {}

    augmented: list[dict] = []
    total = len(rows)

    for i, row in enumerate(rows, 1):
        doc_id = row.get(id_col, f"row_{i}")
        text   = row.get("text", "")
        if not text.strip():
            continue

        for pivot in args.pivot_langs:
            aug_id = f"{doc_id}_bt_{pivot.lower()}"

            if aug_id in checkpoint:
                aug_text = checkpoint[aug_id]
                print(f"[{i}/{total}] {aug_id} (checkpoint)")
            else:
                try:
                    aug_text = back_translate(text, pivot)
                except Exception as e:
                    print(f"[{i}/{total}] {aug_id} ERROR: {e}", file=sys.stderr)
                    continue

                checkpoint[aug_id] = aug_text
                _save_ckpt(ckpt_path, checkpoint)
                print(f"[{i}/{total}] {aug_id} ({len(text)} → {len(aug_text)} chars)")

            aug_row         = dict(row)
            aug_row[id_col] = aug_id
            aug_row["text"] = aug_text
            augmented.append(aug_row)

    _write_csv(args.output_file, fieldnames, rows + augmented)
    print(f"\n[augment] {len(rows)} originales + {len(augmented)} aumentadas "
          f"= {len(rows) + len(augmented)} filas → {args.output_file}")

    if ckpt_path.exists():
        ckpt_path.unlink()


if __name__ == "__main__":
    main()
