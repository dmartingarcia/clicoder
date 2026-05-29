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

    def _post(self, body: list[dict], src_lang: str, tgt_lang: str):
        import time
        params  = {"api-version": "3.0", "from": src_lang, "to": tgt_lang}
        headers = {
            "Ocp-Apim-Subscription-Key":    self.key,
            "Ocp-Apim-Subscription-Region": self.region,
            "Content-Type": "application/json",
        }
        retries = 0
        while True:
            resp = self._requests.post(
                AZURE_ENDPOINT, params=params, headers=headers,
                json=body, timeout=60,
            )
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 0))
                wait = retry_after if retry_after > 0 else 10
                retries += 1
                for remaining in range(wait, 0, -1):
                    print(f"\r[azure] 429 rate-limit (retry #{retries}) — {remaining:2d}s…  ", end="", flush=True)
                    time.sleep(1)
                print(f"\r[azure] 429 rate-limit (retry #{retries}) — reintentando…          ")
                continue
            retries = 0
            resp.raise_for_status()
            return resp.json()

    def translate(self, texts: list[str], src_lang: str, tgt_lang: str) -> list[str]:
        results = []
        for i in range(0, len(texts), AZURE_BATCH):
            batch = texts[i : i + AZURE_BATCH]
            body  = [{"text": t} for t in batch]
            for item in self._post(body, src_lang, tgt_lang):
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



def _write_csv(path: str, fieldnames: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _append_row(path: str, fieldnames: list[str], row: dict) -> None:
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=fieldnames).writerow(row)


def _count_rows(path: str) -> int:
    _, rows = _read_csv(path)
    return len(rows)


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
    parser.add_argument("--only_row",     type=int, default=None,
                        help="Traduce solo la fila N (1-indexed) y la añade al CSV de salida existente")
    args = parser.parse_args()

    fieldnames, rows = _read_csv(args.input_file)
    total_chars = sum(len(r.get("text", "")) for r in rows)

    print(f"[augment] backend: {args.backend} | {len(rows)} notas | {total_chars:,} chars | pivots: {args.pivot_langs}")
    print(f"[augment] augmentaciones: {len(rows) * len(args.pivot_langs)} notas nuevas "
          f"→ dataset total: {len(rows) * (1 + len(args.pivot_langs))} notas")

    if args.backend == "azure":
        azure_chars = total_chars * len(args.pivot_langs) * 2
        print(f"[augment] Azure chars estimados: {azure_chars:,} (free tier: 2,000,000/mes)")

    if args.dry_run:
        print("[augment] --dry_run: sin traducción. Saliendo.")
        return

    # Inicializar backend
    if args.backend == "nllb":
        translator     = NLLBTranslator(args.nllb_model, batch_size=args.nllb_batch)
        back_translate = lambda text, pivot: back_translate_nllb(translator, text, pivot)
    else:
        translator     = AzureTranslator(args.azure_key, args.azure_region)
        back_translate = lambda text, pivot: back_translate_azure(translator, text, pivot)

    base   = Path(args.output_file)
    stem   = base.stem   # e.g. codiesp_D_source_train_augmented
    suffix = base.suffix  # .csv
    parent = base.parent

    total = len(rows)

    for pivot in args.pivot_langs:
        out_path = parent / f"{stem}_{args.backend}_{pivot.lower()}{suffix}"

        if args.only_row is not None:
            if not out_path.exists():
                print(f"[augment] ERROR: {out_path.name} no existe; lanza sin --only_row primero.", file=sys.stderr)
                continue
            print(f"\n[augment] pivot={pivot} → {out_path.name} | solo fila {args.only_row}")
        elif args.resume and out_path.exists():
            already_done = _count_rows(str(out_path)) - len(rows)
            print(f"\n[augment] pivot={pivot} → {out_path.name} | resume: {already_done} traducciones ya guardadas")
        else:
            _write_csv(str(out_path), fieldnames, rows)
            already_done = 0
            print(f"\n[augment] pivot={pivot} → {out_path.name}")

        n_done    = 0
        char_diffs: list[int] = []
        word_diffs: list[int] = []

        for i, row in enumerate(rows, 1):
            text = row.get("text", "")
            if not text.strip():
                continue

            if args.only_row is not None:
                if i != args.only_row:
                    continue
            elif n_done < already_done:
                n_done += 1
                print(f"[{i}/{total}] (ya procesado)")
                continue

            retry = 0
            while True:
                try:
                    aug_text = back_translate(text, pivot)
                    break
                except Exception as e:
                    retry += 1
                    wait = min(10 * retry, 120)
                    print(f"[{i}/{total}] ERROR (intento #{retry}): {e} — reintentando en {wait}s…", file=sys.stderr)
                    import time; time.sleep(wait)

            aug_row         = dict(row)
            aug_row["text"] = aug_text
            _append_row(str(out_path), fieldnames, aug_row)
            n_done += 1

            delta_c = len(aug_text) - len(text)
            delta_w = len(aug_text.split()) - len(text.split())
            char_diffs.append(delta_c)
            word_diffs.append(delta_w)
            print(f"[{i}/{total}] chars: {len(text)}→{len(aug_text)} ({delta_c:+d})  "
                  f"palabras: {len(text.split())}→{len(aug_text.split())} ({delta_w:+d})")

        print(f"[augment] {len(rows)} originales + {n_done} aumentadas "
              f"= {len(rows) + n_done} filas → {out_path.name}")

        if char_diffs:
            avg_dc = sum(char_diffs) / len(char_diffs)
            avg_dw = sum(word_diffs) / len(word_diffs)
            changed = sum(1 for d in char_diffs if d != 0)
            print(f"[augment] Δchars media: {avg_dc:+.1f}  |  Δpalabras media: {avg_dw:+.1f}  |  "
                  f"notas con cambio: {changed}/{len(char_diffs)} ({100*changed/len(char_diffs):.1f}%)")


if __name__ == "__main__":
    main()
