"""
augment_paraphrase.py — Paráfrasis de notas clínicas con Gemma 3 4B IT (GPU).

Genera versiones paráfraseadas manteniendo todos los detalles médicos intactos
(diagnósticos, fármacos, dosis, fechas, procedimientos). Las etiquetas CIE-10
se copian sin cambio.

Uso:
    python augment_paraphrase.py
    python augment_paraphrase.py --n_per_note 2 --temperature 0.8
    python augment_paraphrase.py --dry_run
    python augment_paraphrase.py --resume
"""

import argparse
import csv
import os
import sys
from pathlib import Path

import torch
from huggingface_hub import snapshot_download
from transformers import AutoModelForCausalLM, AutoTokenizer

# Las barras de tqdm de HF no funcionan en Docker sin TTY
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

MODEL_ID = "google/gemma-3-4b-it"
DEFAULT_INPUT = "/data/codiesp_csvs/codiesp_D_source_train.csv"
DEFAULT_OUTPUT = "/data/codiesp_csvs/codiesp_D_source_train_augmented_paraphrase.csv"
MAX_INPUT_WORDS = 800

PARAPHRASE_PROMPT = (
    "Eres un médico experto en documentación clínica. "
    "Reformula el siguiente informe clínico con distintas palabras y estructura, "
    "conservando EXACTAMENTE todos los diagnósticos, fármacos, dosis, fechas, "
    "procedimientos y valores analíticos. No añadas ni omitas información médica.\n\n"
    "Informe original:\n{text}\n\nInforme reformulado:"
)


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------


def load_model(model_id: str, device: str):
    print(f"[paraphrase] descargando/verificando {model_id}…")
    local_path = snapshot_download(
        repo_id=model_id,
        ignore_patterns=[
            "*.msgpack",
            "*.h5",
            "flax_model*",
            "tf_model*",
            "rust_model*",
        ],
    )
    print(f"[paraphrase] modelo en caché: {local_path}")
    print(f"[paraphrase] cargando en {device}…")
    tokenizer = AutoTokenizer.from_pretrained(local_path)
    model = AutoModelForCausalLM.from_pretrained(
        local_path,
        dtype=torch.bfloat16,
        device_map="auto",
    )
    model.eval()
    print("[paraphrase] modelo listo.")
    return tokenizer, model


def paraphrase(
    tokenizer,
    model,
    text: str,
    temperature: float,
    max_new_tokens: int,
    device: str,
) -> str:
    words = text.split()
    if len(words) > MAX_INPUT_WORDS:
        text = " ".join(words[:MAX_INPUT_WORDS])

    messages = [{"role": "user", "content": PARAPHRASE_PROMPT.format(text=text)}]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    input_len = inputs["input_ids"].shape[1]

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=True,
            top_p=0.9,
            repetition_penalty=1.1,
            pad_token_id=tokenizer.eos_token_id,
        )

    new_tokens = outputs[0][input_len:]
    result = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    for prefix in ("Informe reformulado:", "Reformulado:", "**Informe reformulado:**"):
        if result.startswith(prefix):
            result = result[len(prefix) :].strip()

    return result or text


# ---------------------------------------------------------------------------
# CSV / checkpoint helpers
# ---------------------------------------------------------------------------


def _read_csv(path: str) -> tuple[list[str], list[dict]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return fieldnames, rows


def _write_csv(path: str, fieldnames: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _append_row(path: str, fieldnames: list[str], row: dict) -> None:
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=fieldnames).writerow(row)


def _count_augmented(path: str, n_originals: int) -> int:
    with open(path, newline="", encoding="utf-8") as f:
        total = sum(1 for _ in csv.DictReader(f))
    return max(0, total - n_originals)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_file", default=DEFAULT_INPUT)
    parser.add_argument("--output_file", default=DEFAULT_OUTPUT)
    parser.add_argument("--model_id", default=MODEL_ID)
    parser.add_argument(
        "--n_per_note", type=int, default=1, help="Paráfrasis por nota (default: 1)"
    )
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max_new_tokens", type=int, default=1200)
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    fieldnames, rows = _read_csv(args.input_file)
    total_notes = len(rows)
    total_chars = sum(len(r.get("text", "")) for r in rows)

    print(
        f"[paraphrase] modelo: {args.model_id} | {total_notes} notas | "
        f"{total_chars:,} chars | {args.n_per_note} paráfrasis/nota"
    )
    print(
        f"[paraphrase] output: {args.output_file} | "
        f"dataset final: {total_notes * (1 + args.n_per_note)} notas"
    )

    if args.dry_run:
        print("[paraphrase] --dry_run: sin generación. Saliendo.")
        return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print(
            "[paraphrase] AVISO: CUDA no disponible, corriendo en CPU (muy lento).",
            file=sys.stderr,
        )

    tokenizer, model = load_model(args.model_id, device)

    out_path = Path(args.output_file)
    if args.resume and out_path.exists():
        already_done = _count_augmented(str(out_path), total_notes)
        print(f"[paraphrase] resume: {already_done} paráfrasis ya guardadas")
    else:
        _write_csv(str(out_path), fieldnames, rows)
        already_done = 0

    n_done = 0
    char_diffs: list[int] = []
    word_diffs: list[int] = []

    for pass_i in range(args.n_per_note):
        for i, row in enumerate(rows, 1):
            global_idx = pass_i * total_notes + (i - 1)
            if global_idx < already_done:
                n_done += 1
                print(f"[pass {pass_i + 1}/{args.n_per_note}][{i}/{total_notes}] (ya procesado)")
                continue

            text = row.get("text", "")
            if not text.strip():
                continue

            retry = 0
            while True:
                try:
                    aug_text = paraphrase(
                        tokenizer,
                        model,
                        text,
                        args.temperature,
                        args.max_new_tokens,
                        device,
                    )
                    break
                except Exception as e:
                    retry += 1
                    wait = min(10 * retry, 60)
                    print(
                        f"[{i}/{total_notes}] ERROR (intento #{retry}): {e} — reintentando en {wait}s…",
                        file=sys.stderr,
                    )
                    import time

                    time.sleep(wait)

            aug_row = dict(row)
            aug_row["text"] = aug_text
            _append_row(str(out_path), fieldnames, aug_row)
            n_done += 1

            delta_c = len(aug_text) - len(text)
            delta_w = len(aug_text.split()) - len(text.split())
            char_diffs.append(delta_c)
            word_diffs.append(delta_w)
            print(
                f"[pass {pass_i + 1}/{args.n_per_note}][{i}/{total_notes}] "
                f"chars: {len(text)}→{len(aug_text)} ({delta_c:+d})  "
                f"palabras: {len(text.split())}→{len(aug_text.split())} ({delta_w:+d})"
            )

    print(
        f"[paraphrase] {total_notes} originales + {n_done} paráfrasis "
        f"= {total_notes + n_done} filas → {out_path.name}"
    )
    if char_diffs:
        avg_dc = sum(char_diffs) / len(char_diffs)
        avg_dw = sum(word_diffs) / len(word_diffs)
        changed = sum(1 for d in char_diffs if d != 0)
        print(
            f"[paraphrase] Δchars media: {avg_dc:+.1f}  |  Δpalabras media: {avg_dw:+.1f}  |  "
            f"notas con cambio: {changed}/{len(char_diffs)} ({100 * changed / len(char_diffs):.1f}%)"
        )


if __name__ == "__main__":
    main()
