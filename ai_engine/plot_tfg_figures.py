# Genera figuras de datos para el TFG (PNG) a partir de datos reales.
# Ejecutar en el contenedor ai_engine:  python plot_tfg_figures.py
# Salida por defecto: /app/model/tfg_*.png  (después copiar a tfg/figs/)

import csv
import json
import os
from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OUT_DIR", os.path.join(HERE, "model"))
TRAIN = os.environ.get("TRAIN_FILE", "/data/codiesp_csvs/codiesp_D_source_train.csv")
EVAL = os.path.join(HERE, "model", "eval_test.json")

TEAL, ORANGE, GREY = "#2a7f9e", "#c46210", "#8aa0ab"


def parse_labels(s):
    return [c.strip().upper() for c in str(s).split(";") if c.strip()]


# --- 1. Cola larga de frecuencias de códigos ---
freq = Counter()
with open(TRAIN, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        for c in parse_labels(row.get("labels", "")):
            freq[c] += 1
counts = sorted(freq.values(), reverse=True)
once = sum(1 for v in counts if v == 1)
fig, ax = plt.subplots(figsize=(6, 4))
ax.loglog(range(1, len(counts) + 1), counts, marker=".", linestyle="none", color=TEAL)
ax.set_xlabel("Rango del código (ordenado por frecuencia)")
ax.set_ylabel("N.º de documentos en que aparece")
ax.set_title(
    f"Frecuencia de códigos: distribución de cola larga\n"
    f"{len(counts)} códigos · {once} ({100 * once / len(counts):.0f} %) aparecen una sola vez"
)
ax.grid(True, which="both", ls=":", alpha=0.4)
fig.tight_layout()
fig.savefig(f"{OUT}/tfg_longtail.png", dpi=150)
plt.close(fig)

# --- 2. Barrido de umbral global (val + test) ---
with open(EVAL, encoding="utf-8") as f:
    ev = json.load(f)
sw = ev["sweep"]
th = [r["threshold"] for r in sw]
best = ev["best_threshold_val"]
fig, ax = plt.subplots(figsize=(6, 4))
ax.plot(th, [r["val"]["f1_micro"] for r in sw], marker="o", color=TEAL, label="F1-micro (val)")
ax.plot(th, [r["test"]["f1_micro"] for r in sw], marker="s", color=ORANGE, label="F1-micro (test)")
ax.plot(
    th,
    [r["val"]["f1_macro"] for r in sw],
    marker="o",
    ls="--",
    color=TEAL,
    alpha=0.6,
    label="F1-macro (val)",
)
ax.plot(
    th,
    [r["test"]["f1_macro"] for r in sw],
    marker="s",
    ls="--",
    color=ORANGE,
    alpha=0.6,
    label="F1-macro (test)",
)
ax.axvline(best, color="gray", ls=":", label=f"óptimo en val = {best}")
ax.set_xlabel("Umbral global de decisión")
ax.set_ylabel("F1")
ax.set_title("Barrido del umbral de decisión")
ax.legend(fontsize=8)
ax.grid(True, ls=":", alpha=0.4)
fig.tight_layout()
fig.savefig(f"{OUT}/tfg_threshold.png", dpi=150)
plt.close(fig)

# --- 3. Benchmark CodiEsp-D 2020: MAP por sistema (test) ---
systems = [
    ("IXA-AAA", 0.593),
    ("IAM", 0.521),
    ("FLE", 0.519),
    ("The Mental Strokers", 0.517),
    ("LSI-UNED", 0.517),
    ("Anuj", 0.505),
    ("MEDIA", 0.488),
    ("ICB-UMA", 0.482),
    ("IMS", 0.449),
    ("Este trabajo", 0.437),
]
systems.sort(key=lambda s: -s[1])
names = [s[0] for s in systems]
maps = [s[1] for s in systems]
colors = [ORANGE if n == "Este trabajo" else GREY for n in names]
fig, ax = plt.subplots(figsize=(7, 4))
y = np.arange(len(names))
ax.barh(y, maps, color=colors)
ax.set_yticks(y)
ax.set_yticklabels(names, fontsize=8)
ax.invert_yaxis()
ax.set_xlabel("MAP por documento (conjunto de prueba)")
ax.set_title("CodiEsp-D 2020: MAP por sistema")
for i, v in enumerate(maps):
    ax.text(v + 0.006, i, f"{v:.3f}", va="center", fontsize=7)
ax.set_xlim(0, 0.65)
ax.grid(True, axis="x", ls=":", alpha=0.4)
fig.tight_layout()
fig.savefig(f"{OUT}/tfg_benchmark.png", dpi=150)
plt.close(fig)

# --- 4. Contribución acumulada de cada técnica (F1-micro val, umbral 0,3) ---
steps = [
    ("Código completo\n(sin preentr.)", 0.327),
    ("+ Preentr.\nCIE-10", 0.431),
    ("+ Snippets\ntask_X", 0.470),
    ("+ Reduce\nLROnPlateau", 0.475),
    ("+ Smoothing +\ndescongelado", 0.484),
    ("+ Consist.\njerárquica", 0.489),
]
labels = [s[0] for s in steps]
vals = [s[1] for s in steps]
fig, ax = plt.subplots(figsize=(7, 4))
x = np.arange(len(vals))
ax.plot(x, vals, marker="o", color=TEAL)
ax.fill_between(x, 0.30, vals, alpha=0.12, color=TEAL)
for i, v in enumerate(vals):
    ax.text(i, v + 0.004, f"{v:.3f}", ha="center", fontsize=7)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=7)
ax.set_ylim(0.30, 0.51)
ax.set_ylabel("F1-micro (validación, umbral 0,3)")
ax.set_title("Contribución acumulada de cada técnica")
ax.grid(True, axis="y", ls=":", alpha=0.4)
fig.tight_layout()
fig.savefig(f"{OUT}/tfg_waterfall.png", dpi=150)
plt.close(fig)

# --- 5. Longitud en tokens por conjunto (train/val/test) ---
tl = ev.get("token_lengths", {})
if isinstance(tl, dict) and tl:
    order = [k for k in ("train", "val", "test") if k in tl]
    data = [np.array(tl[k]) for k in order]
    labels = [f"{k}\n{100 * (d > 512).mean():.0f}% >512" for k, d in zip(order, data, strict=False)]
    fig, ax = plt.subplots(figsize=(6, 4))
    bp = ax.boxplot(data, patch_artist=True, showmeans=True)
    for patch in bp["boxes"]:
        patch.set_facecolor(TEAL)
        patch.set_alpha(0.5)
    ax.set_xticklabels(labels)
    ax.axhline(512, color=ORANGE, ls="--", lw=2, label="512 tokens (ventana del modelo)")
    ax.set_ylabel("Longitud del informe (tokens)")
    ax.set_title("Longitud en tokens por conjunto (train / val / test)")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", ls=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(f"{OUT}/tfg_tokens.png", dpi=150)
    plt.close(fig)

# --- 6. F1-micro por capítulo CIE-10 (con soporte, sin capítulos de soporte marginal) ---
MIN_SUPPORT = 10
pc = ev.get("per_chapter", {})
if pc:
    kept = {k: v for k, v in pc.items() if v["support"] >= MIN_SUPPORT}
    dropped = sorted(k for k, v in pc.items() if v["support"] < MIN_SUPPORT)
    items = sorted(kept.items(), key=lambda kv: kv[1]["f1_micro"], reverse=True)
    chs = [f"{k}  (n={v['support']})" for k, v in items]
    f1s = [v["f1_micro"] for _, v in items]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    yy = np.arange(len(chs))
    ax.barh(yy, f1s, color=TEAL)
    ax.set_yticks(yy)
    ax.set_yticklabels(chs, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("F1-micro (test, umbral 0,3)")
    ax.set_title("F1-micro por capítulo CIE-10 (soporte entre paréntesis)")
    for i, v in enumerate(f1s):
        ax.text(v + 0.005, i, f"{v:.2f}", va="center", fontsize=7)
    if dropped:
        ax.text(
            0.98,
            0.02,
            f"Excluidos por soporte < {MIN_SUPPORT}: {', '.join(dropped)}",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=6.5,
            color=GREY,
        )
    ax.grid(True, axis="x", ls=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(f"{OUT}/tfg_chapters.png", dpi=150)
    plt.close(fig)

# --- 7. Curva precisión-recall a partir del barrido de umbral ---
sweep = ev.get("sweep", [])
if sweep:
    rs = [r["test"]["r_micro"] for r in sweep]
    ps = [r["test"]["p_micro"] for r in sweep]
    ths = [r["threshold"] for r in sweep]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(rs, ps, marker="o", ms=3.5, color=TEAL, label="Conjunto de prueba")
    if "val" in sweep[0]:
        ax.plot(
            [r["val"]["r_micro"] for r in sweep],
            [r["val"]["p_micro"] for r in sweep],
            marker="o",
            ms=3.5,
            ls="--",
            color=GREY,
            label="Validación",
        )
    for r, pr, t in zip(rs, ps, ths, strict=False):
        if abs(t - 0.3) < 1e-9:
            ax.plot([r], [pr], marker="o", ms=11, mfc="none", mec=ORANGE, mew=2)
            ax.annotate(
                "umbral 0,3\n(producción)",
                (r, pr),
                textcoords="offset points",
                xytext=(12, 10),
                fontsize=7.5,
                color=ORANGE,
            )
    ax.set_xlabel("Recall micro")
    ax.set_ylabel("Precisión micro")
    ax.set_title("Curva precisión-recall (barrido del umbral global)")
    ax.legend(fontsize=8)
    ax.grid(True, ls=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(f"{OUT}/tfg_pr_curve.png", dpi=150)
    plt.close(fig)

# --- 8. F1 sobre test según la frecuencia del código en entrenamiento ---
pf = ev.get("per_train_freq", {})
if pf:
    order = [k for k in ("1", "2-5", "6-20", ">20") if k in pf]
    f1mi = [pf[k]["f1_micro"] for k in order]
    rmi = [pf[k]["r_micro"] for k in order]
    fig, ax = plt.subplots(figsize=(6.5, 4))
    x = np.arange(len(order))
    w = 0.38
    ax.bar(x - w / 2, f1mi, w, color=TEAL, label="F1-micro")
    ax.bar(x + w / 2, rmi, w, color=ORANGE, alpha=0.85, label="Recall micro")
    for i, (a, b) in enumerate(zip(f1mi, rmi, strict=False)):
        ax.text(i - w / 2, a + 0.008, f"{a:.2f}", ha="center", fontsize=7)
        ax.text(i + w / 2, b + 0.008, f"{b:.2f}", ha="center", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels(
        [f"{k}\n{pf[k]['n_codigos']} códigos\n{pf[k]['support']} pares" for k in order],
        fontsize=7.5,
    )
    ax.set_xlabel("Apariciones del código en el corpus de entrenamiento")
    ax.set_ylabel("Métrica sobre el conjunto de prueba")
    ax.set_title("Rendimiento según la frecuencia de entrenamiento del código")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", ls=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(f"{OUT}/tfg_freq.png", dpi=150)
    plt.close(fig)

print("OK: figuras generadas en", OUT)
for n in (
    "tfg_longtail",
    "tfg_threshold",
    "tfg_benchmark",
    "tfg_waterfall",
    "tfg_tokens",
    "tfg_chapters",
    "tfg_pr_curve",
    "tfg_freq",
):
    print("  ", n + ".png")
