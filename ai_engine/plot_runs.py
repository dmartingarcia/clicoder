"""
plot_runs.py — Comparative charts for all training runs.

Generates two files:
  all_trainings_graph.png  — bar chart comparing final metrics per run
  all_epochs_graph.png     — line chart comparing F1-micro curve per epoch across runs

Usage: python plot_runs.py [--csv model/training_runs.csv] [--out model/all_trainings_graph.png]
"""

import argparse
import csv
import json
import pathlib

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

STEP_LABELS = {
    "20260318T214627Z": "3\n(b4×4, thr=0.2\nmax=1024)",
    "20260318T220744Z": "4\n(b8×2, thr=0.3\nbf16 bug)",
    "20260318T221746Z": "5a\n(b8×2, thr=0.3\nfixed)",
    "20260318T222117Z": "5b\n(early stop\npat=5)",
    "20260318T222430Z": "6\n(40 epochs\npat=8)",
    "20260318T224802Z": "7\n(max=1504\nb4×4)",
    "20260318T225344Z": "7b\n(max=1024\nrerun)",
    "20260318T225922Z": "8\n(thr=0.5\nfix bug)",
}


def load_csv(path: str):
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row:
                rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="model/training_runs.csv")
    parser.add_argument("--out", default="model/all_trainings_graph.png")
    args = parser.parse_args()

    script_dir = pathlib.Path(__file__).parent
    rows = load_csv(script_dir / args.csv)

    timestamps = [r["timestamp"] for r in rows]
    labels = [STEP_LABELS.get(ts, ts[-6:]) for ts in timestamps]
    x = np.arange(len(rows))

    f1_micro = [float(r["val_f1_micro"]) for r in rows]
    p_micro = [float(r["val_p_micro"]) for r in rows]
    r_micro = [float(r["val_r_micro"]) for r in rows]
    f1_macro = [float(r["val_f1_macro"]) for r in rows]
    epochs = [int(r["epochs_run"]) for r in rows]
    threshold = [float(r["threshold"]) for r in rows]
    max_len = [int(r["max_length"]) for r in rows]

    # ── colours by threshold ──────────────────────────────────────────────────
    thr_colours = {0.2: "#4e79a7", 0.3: "#f28e2b", 0.5: "#59a14f"}
    bar_colours = [thr_colours.get(t, "#b07aa1") for t in threshold]

    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
    fig.suptitle(
        "CIE-10 mmBERT-base — Comparativa de runs\n"
        "CodiESP  |  ~500 train / 250 val  |  809 códigos (bloque)",
        fontsize=13,
        fontweight="bold",
    )

    # ── panel 1: F1-micro + P + R ──────────────────────────────────────────────
    ax = axes[0]
    w = 0.25
    ax.bar(x - w, f1_micro, width=w, color=bar_colours, label="F1-micro", alpha=0.9)
    ax.bar(x, p_micro, width=w, color=bar_colours, label="P-micro", alpha=0.5)
    ax.bar(x + w, r_micro, width=w, color=bar_colours, label="R-micro", alpha=0.3)
    for i, v in enumerate(f1_micro):
        ax.text(
            x[i] - w,
            v + 0.003,
            f"{v:.3f}",
            ha="center",
            va="bottom",
            fontsize=7.5,
            fontweight="bold",
        )
    ax.set_ylabel("Score (micro)")
    ax.set_ylim(0, max(max(f1_micro), max(p_micro), max(r_micro)) * 1.20 + 0.02)
    ax.set_title("F1-micro / Precision / Recall  (micro-averaged)", fontsize=10)
    ax.legend(["F1-micro", "P-micro", "R-micro"], fontsize=8, loc="upper left")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # threshold legend patches
    patches = [mpatches.Patch(color=c, label=f"thr={t}") for t, c in thr_colours.items()]
    ax.legend(handles=patches, title="Threshold", fontsize=8, loc="upper right")

    # ── panel 2: F1-macro ──────────────────────────────────────────────────────
    ax2 = axes[1]
    ax2.bar(x, f1_macro, color=bar_colours, alpha=0.85)
    for i, v in enumerate(f1_macro):
        ax2.text(x[i], v + 0.001, f"{v:.3f}", ha="center", va="bottom", fontsize=7.5)
    ax2.set_ylabel("F1-macro")
    ax2.set_ylim(0, max(f1_macro) * 1.25 + 0.005)
    ax2.set_title("F1-macro  (per-class average)", fontsize=10)
    ax2.grid(axis="y", linestyle="--", alpha=0.4)

    # ── panel 3: epochs run + max_length ─────────────────────────────────
    ax3 = axes[2]
    ax3b = ax3.twinx()
    ax3.bar(x - 0.15, epochs, width=0.3, color="#76b7b2", alpha=0.85, label="Epochs run")
    ax3b.bar(x + 0.15, max_len, width=0.3, color="#edc948", alpha=0.7, label="max_length")
    ax3.set_ylabel("Epochs run", color="#76b7b2")
    ax3b.set_ylabel("max_length", color="#edc948")
    ax3.set_title("Epochs run  /  max_length per run", fontsize=10)
    lines = [
        mpatches.Patch(color="#76b7b2", label="Epochs run"),
        mpatches.Patch(color="#edc948", label="max_length"),
    ]
    ax3.legend(handles=lines, fontsize=8)
    ax3.grid(axis="y", linestyle="--", alpha=0.4)

    # x-axis labels
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(labels, fontsize=8)
    axes[-1].set_xlabel("Run (paso)")

    plt.tight_layout()
    out_path = script_dir / args.out
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"[ok] guardado en {out_path}")

    # ── epoch comparison chart ────────────────────────────────────────────────
    history_files = sorted((script_dir / "model").glob("training_history_*.json"))
    if history_files:
        _plot_epochs(history_files, script_dir / "model/all_epochs_graph.png")


def _plot_epochs(history_files: list, out_path: pathlib.Path):
    """Line chart: F1-micro and train loss per epoch, one line per run."""
    COLOURS = [
        "#4e79a7",
        "#f28e2b",
        "#59a14f",
        "#e15759",
        "#76b7b2",
        "#edc948",
        "#b07aa1",
        "#ff9da7",
    ]

    # Collect unique models for subtitle
    models_seen = []
    for path in history_files:
        with open(path) as f:
            m = json.load(f).get("model_name", "")
        if m and m not in models_seen:
            models_seen.append(m)
    models_str = ", ".join(models_seen)

    fig, (ax_f1, ax_loss) = plt.subplots(2, 1, figsize=(14, 9), sharex=False)
    fig.suptitle(
        f"CIE-10 — Curvas de entrenamiento por época (todos los runs)\n"
        f"{models_str}  |  CodiESP  |  ~500 train / 250 val",
        fontsize=12,
        fontweight="bold",
    )

    for i, path in enumerate(history_files):
        with open(path) as f:
            data = json.load(f)
        ts = data["timestamp"]
        model = data.get("model_name", "").split("/")[-1]  # short name
        thr = data.get("threshold", "?")
        mx = data.get("max_length", "?")
        label = (
            f"{STEP_LABELS.get(ts, ts[-6:]).replace(chr(10), ' ')}  [{model} thr={thr} max={mx}]"
        )
        colour = COLOURS[i % len(COLOURS)]
        history = data["history"]
        epochs = [h["epoch"] for h in history]
        f1 = [h["val_f1_micro"] for h in history]
        loss = [h["train_loss"] for h in history]

        ax_f1.plot(
            epochs,
            f1,
            color=colour,
            linewidth=1.8,
            marker="o",
            markersize=3,
            label=label,
        )
        ax_loss.plot(
            epochs,
            loss,
            color=colour,
            linewidth=1.8,
            marker="o",
            markersize=3,
            label=label,
        )

    ax_f1.set_ylabel("Val F1-micro")
    ax_f1.set_title("Val F1-micro por época", fontsize=10)
    ax_f1.grid(linestyle="--", alpha=0.4)
    ax_f1.legend(fontsize=7, loc="lower right")

    ax_loss.set_ylabel("Train loss")
    ax_loss.set_xlabel("Época")
    ax_loss.set_title("Train loss por época", fontsize=10)
    ax_loss.grid(linestyle="--", alpha=0.4)
    ax_loss.legend(fontsize=7, loc="upper right")

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] guardado en {out_path}")


if __name__ == "__main__":
    main()
