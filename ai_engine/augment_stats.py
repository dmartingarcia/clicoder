import csv
import statistics
import sys
from collections import Counter
from pathlib import Path

PIVOTS = ("en", "de", "fr")
EDGES = (-20, -15, -10, -5, 0, 5, 10, 15, 20)


def read(path):
    with open(path, encoding="utf8", newline="") as f:
        return list(csv.DictReader(f))


def labels(row):
    return [c for c in row["labels"].split(";") if c]


def bucket(delta):
    for i, edge in enumerate(EDGES):
        if delta <= edge:
            return i
    return len(EDGES)


def main(folder):
    folder = Path(folder)
    original = read(folder / "codiesp_D_source_train.csv")
    freq = Counter(c for r in original for c in labels(r))
    n = len(freq)
    print("Distribución de frecuencias de códigos")
    for name, k in (("= 1", 1), ("<= 2", 2), ("<= 5", 5)):
        m = sum(1 for v in freq.values() if (v == 1 if k == 1 else v <= k))
        print(f"  {name}: {m} ({100 * m / n:.1f} %)")
    m = sum(1 for v in freq.values() if v > 5)
    print(f"  > 5: {m} ({100 * m / n:.1f} %); total {n}")

    docs, annotations, chars = (
        len(original),
        sum(len(labels(r)) for r in original),
        sum(len(r["text"]) for r in original),
    )
    print("\nCorpus por etapa")
    print(
        f"  original: docs={docs} codigos={n} anotaciones={annotations} media={annotations / docs:.2f} caracteres={chars}"
    )
    for p in PIVOTS:
        rows = read(folder / f"codiesp_D_source_train_augmented_azure_{p}.csv")
        new = rows[len(original) :]
        docs += len(new)
        annotations += sum(len(labels(r)) for r in new)
        chars += sum(len(r["text"]) for r in new)
        print(
            f"  + {p}: docs={docs} anotaciones={annotations} media={annotations / docs:.2f} caracteres={chars}"
        )

    print("\nCalidad de la retrotraducción")
    for p in PIVOTS:
        rows = read(folder / f"codiesp_D_source_train_augmented_azure_{p}.csv")
        new = rows[len(original) :]
        dc = [len(b["text"]) - len(a["text"]) for a, b in zip(original, new, strict=True)]
        dw = [
            len(b["text"].split()) - len(a["text"].split())
            for a, b in zip(original, new, strict=True)
        ]
        changed = sum(1 for d in dc if d != 0)
        print(f"  {p}: variación léxica {changed}/{len(new)} ({100 * changed / len(new):.1f} %)")
        print(
            f"    caracteres media {statistics.mean(dc):+.1f} mediana {statistics.median(dc):+.1f} rango {min(dc)} a {max(dc)}"
        )
        print(
            f"    palabras media {statistics.mean(dw):+.1f} mediana {statistics.median(dw):+.1f} rango {min(dw)} a {max(dw)}"
        )
        hist = Counter(bucket(d) for d in dw)
        print("    intervalos:", [hist.get(i, 0) for i in range(len(EDGES) + 1)])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/data/codiesp_csvs")
