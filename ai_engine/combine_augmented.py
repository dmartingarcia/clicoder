"""
combine_augmented.py — Combina el corpus original con las variantes aumentadas de todos los pivotes.

Uso:
    python combine_augmented.py
    python combine_augmented.py --input_dir /data/codiesp_csvs --pivots azure_en azure_de azure_fr
"""

import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input_dir",
        default="/data/codiesp_csvs",
        help="Directorio con los CSV de entrenamiento",
    )
    parser.add_argument(
        "--orig_file",
        default="codiesp_D_source_train.csv",
        help="CSV original (sin aumentar)",
    )
    parser.add_argument(
        "--pivots",
        nargs="+",
        default=["azure_en", "azure_de", "azure_fr"],
        help="Sufijos de los ficheros aumentados (default: azure_en azure_de azure_fr)",
    )
    parser.add_argument(
        "--output_file",
        default="codiesp_D_source_train_augmented_all.csv",
        help="Nombre del CSV de salida",
    )
    args = parser.parse_args()

    base_dir = Path(args.input_dir)
    orig_path = base_dir / args.orig_file

    with open(orig_path, newline="", encoding="utf-8") as f:
        orig_rows = list(csv.DictReader(f))
    fieldnames = list(orig_rows[0].keys())
    n_orig = len(orig_rows)

    all_rows = list(orig_rows)

    for pivot in args.pivots:
        aug_path = base_dir / f"codiesp_D_source_train_augmented_{pivot}.csv"
        if not aug_path.exists():
            print(f"[combine] AVISO: no encontrado {aug_path.name}, saltando")
            continue
        with open(aug_path, newline="", encoding="utf-8") as f:
            aug_rows = list(csv.DictReader(f))
        added = aug_rows[n_orig:]
        all_rows.extend(added)
        print(f"[combine] {pivot}: +{len(added)} notas aumentadas")

    out_path = base_dir / args.output_file
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_rows)

    print(
        f"[combine] {n_orig} originales + {len(all_rows) - n_orig} aumentadas = {len(all_rows)} filas → {out_path.name}"
    )


if __name__ == "__main__":
    main()
