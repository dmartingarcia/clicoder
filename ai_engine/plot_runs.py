"""
plot_runs.py: Comparative charts for all training runs.

Genera dos ficheros para la memoria (texto de ejes en español, coma decimal):
  all_trainings_graph.png : F1-micro de validación y épocas de cada ejecución
  all_epochs_graph.png    : curvas por época, con dos ejecuciones resaltadas

Usage: python plot_runs.py [--csv model/training_runs.csv] [--out model/all_trainings_graph.png]
"""

import argparse
import csv
import json
import pathlib

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter


def load_csv(path: str):
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row:
                rows.append(row)
    return rows


def _comma(ax, axis="y"):
    fmt = FuncFormatter(lambda v, _: f"{v:g}".replace(".", ","))
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="model/training_runs.csv")
    parser.add_argument("--out", default="model/all_trainings_graph.png")
    args = parser.parse_args()

    script_dir = pathlib.Path(__file__).parent
    rows = load_csv(script_dir / args.csv)
    x = np.arange(1, len(rows) + 1)
    f1 = np.array([float(r["val_f1_micro"]) for r in rows])
    epochs = np.array([int(r["epochs_run"]) for r in rows])
    codes = np.array([int(r["num_codes"]) for r in rows])

    plt.rcParams.update({"font.size": 11, "axes.titlesize": 12, "axes.labelsize": 11})
    fig, (ax, ax2) = plt.subplots(
        2, 1, figsize=(8, 6), sharex=True, gridspec_kw={"height_ratios": [3, 1.4]}
    )

    for n, colour, label in [
        (809, "#f28e2b", "809 clases (bloques)"),
        (1767, "#4e79a7", "1.767 clases (códigos completos)"),
    ]:
        m = codes == n
        ax.scatter(x[m], f1[m], s=22, color=colour, label=label, zorder=3)
    best = int(np.argmax(np.where(codes == 1767, f1, -1)))
    ax.scatter(
        [x[best]], [f1[best]], s=90, facecolors="none", edgecolors="black", linewidths=1.5, zorder=4
    )
    ax.annotate(
        f"mejor: {f1[best]:.4f}".replace(".", ","),
        (x[best], f1[best]),
        textcoords="offset points",
        xytext=(-8, -22),
        ha="right",
        fontsize=10,
    )
    ax.set_ylabel("F1-micro de validación")
    ax.grid(linestyle="--", alpha=0.4)
    ax.legend(loc="lower right", fontsize=10)
    _comma(ax)

    ax2.bar(x, epochs, color="#76b7b2", width=0.8)
    ax2.set_ylabel("Épocas")
    ax2.set_xlabel("Ejecución (orden cronológico en training_runs.csv)")
    ax2.grid(axis="y", linestyle="--", alpha=0.4)

    plt.tight_layout()
    out_path = script_dir / args.out
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] guardado en {out_path}")

    history_files = sorted((script_dir / "model").glob("training_history_*.json"))
    if history_files:
        _plot_epochs(history_files, script_dir / "model/all_epochs_graph.png")


HIGHLIGHT = {
    "20260530T030233Z": ("#4e79a7", "Paso 36 (referencia)"),
    "20260915T102909Z": ("#e15759", "c102909 (mejor F1 de validación)"),
}


def _plot_epochs(history_files: list, out_path: pathlib.Path):
    """F1-micro y pérdida por época de cada ejecución."""
    plt.rcParams.update({"font.size": 11, "axes.titlesize": 12, "axes.labelsize": 11})
    fig, (ax_f1, ax_loss) = plt.subplots(2, 1, figsize=(8, 6.5), sharex=True)

    n_bg = 0
    for path in history_files:
        with open(path) as f:
            data = json.load(f)
        if "RigoBERTa-Clinical" not in data.get("model_name", ""):
            continue
        ts = data["timestamp"]
        hist = data["history"]
        ep = [h["epoch"] for h in hist]
        f1 = [h["val_f1_micro"] for h in hist]
        loss = [h["train_loss"] for h in hist]
        if ts in HIGHLIGHT:
            colour, label = HIGHLIGHT[ts]
            kw = {"color": colour, "linewidth": 2.2, "label": label, "zorder": 3}
        else:
            kw = {"color": "#b0b0b0", "linewidth": 0.8, "alpha": 0.6, "zorder": 1}
            n_bg += 1
        ax_f1.plot(ep, f1, **kw)
        ax_loss.plot(ep, loss, **kw)
    ax_f1.plot([], [], color="#b0b0b0", linewidth=1.5, label=f"Otras ejecuciones ({n_bg})")

    ax_f1.set_ylabel("F1-micro de validación")
    ax_f1.legend(loc="lower right", fontsize=10)
    ax_loss.set_ylabel("Pérdida de entrenamiento")
    ax_loss.set_ylim(0, 1)
    ax_loss.set_xlabel("Época")
    for a in (ax_f1, ax_loss):
        a.grid(linestyle="--", alpha=0.4)
        _comma(a)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] guardado en {out_path}")


if __name__ == "__main__":
    main()
