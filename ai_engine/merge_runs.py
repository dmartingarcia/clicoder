"""Fusiona los training_runs.csv de ejecuciones paralelas en el CSV canónico.

Al lanzar varios entrenamientos a la vez, cada uno escribe en su propio --output_dir:
si compartieran directorio se pisarían el config.json y podrían corromper el CSV al
reescribir la cabecera dos procesos a la vez. Este script recoge las filas de cada
directorio y las añade a model/training_runs.csv en orden de timestamp, ampliando la
cabecera si las ejecuciones nuevas traen columnas que antes no existían.

Uso:
  python3 merge_runs.py --runs_dir /app/model/runs --main /app/model/training_runs.csv
"""

import argparse
import csv
from pathlib import Path


def read_rows(path: Path):
    if not path.exists():
        return [], []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        fields = [(k or "").strip() for k in (reader.fieldnames or [])]
        rows = [
            {(k or "").strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()}
            for r in reader
        ]
    return fields, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs_dir", default="/app/model/runs")
    ap.add_argument("--main", default="/app/model/training_runs.csv")
    ap.add_argument("--dry_run", action="store_true")
    args = ap.parse_args()

    main_path = Path(args.main)
    fields, rows = read_rows(main_path)
    known = {r.get("timestamp") for r in rows}
    added = 0

    for sub in sorted(Path(args.runs_dir).glob("*/training_runs.csv")):
        sub_fields, sub_rows = read_rows(sub)
        for extra in [f for f in sub_fields if f not in fields]:
            fields.append(extra)
        for r in sub_rows:
            if r.get("timestamp") in known:
                print(f"[skip] {sub.parent.name}: {r.get('timestamp')} ya estaba")
                continue
            known.add(r.get("timestamp"))
            rows.append(r)
            added += 1
            print(
                f"[add ] {sub.parent.name}: {r.get('timestamp')}  "
                f"F1={r.get('val_f1_micro')}  MAP={r.get('val_map_macro')}"
            )

    if added == 0:
        print("[merge] nada que añadir")
        return

    rows.sort(key=lambda r: r.get("timestamp") or "")
    if args.dry_run:
        print(f"[merge] {added} filas nuevas (dry run, no se escribe)")
        return

    with open(main_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, restval="", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"[merge] {added} filas añadidas → {main_path} ({len(rows)} ejecuciones en total)")


if __name__ == "__main__":
    main()
