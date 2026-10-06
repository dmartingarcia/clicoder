"""Compara dos grupos de ejecuciones por su MAP, con el contraste estadístico correspondiente.

Con 500 documentos de entrenamiento, el ruido entre semillas idénticas es del mismo orden que el
efecto de cualquier cambio que se quiera medir. Comparar una ejecución contra otra -o contra el
máximo de un grupo- produce conclusiones que no se reproducen: a lo largo de esta serie de
experimentos ocurrió dos veces. La única lectura defendible es comparar DISTRIBUCIONES, y decir
explícitamente si la diferencia observada se distingue del azar.

Se aplica la t de Welch (no asume varianzas iguales) y se acompaña de la d de Cohen, porque con
muestras de 4 o 5 ejecuciones un p-valor por sí solo dice poco: interesa también si el efecto es
grande en relación con el ruido.

Uso:
  python3 compare_runs.py --control 0.4315 0.4390 0.4192 0.4317 0.4421 \
                          --tratamiento 0.4535 0.4383 --etiqueta "ZLPR+MAP"
"""

import argparse
import math
import statistics as st


def welch(a: list[float], b: list[float]) -> tuple[float, float, float]:
    """t de Welch, grados de libertad y error estándar de la diferencia de medias."""
    va, vb = st.variance(a), st.variance(b)
    na, nb = len(a), len(b)
    se = math.sqrt(va / na + vb / nb)
    t = (st.mean(b) - st.mean(a)) / se
    num = (va / na + vb / nb) ** 2
    den = (va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1)
    return t, num / den, se


def p_two_sided(t: float, df: float) -> float:
    """p bilateral de la t de Student, por la incompleta beta regularizada."""
    x = df / (df + t * t)
    return _betainc(df / 2, 0.5, x)


def _betainc(a: float, b: float, x: float) -> float:
    """I_x(a,b) por fracción continua (Lentz). Suficiente para los tamaños de aquí."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    if x > (a + 1) / (a + b + 2):
        return 1.0 - _betainc(b, a, 1 - x)
    f, c, d = 1.0, 1.0, 0.0
    for i in range(300):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        d = 1e-30 if abs(d) < 1e-30 else d
        d = 1.0 / d
        c = 1.0 + num / c
        c = 1e-30 if abs(c) < 1e-30 else c
        f *= c * d
        if abs(1.0 - c * d) < 1e-10:
            break
    return front * (f - 1.0)


def t_critico(df: float, conf: float = 0.95) -> float:
    """Cuantil t bilateral por bisección sobre p_two_sided.

    Con muestras de 4 o 5 ejecuciones los grados de libertad son pocos y el cuantil t
    se separa mucho del 1,96 de la normal: usar la aproximación normal produce un
    intervalo más estrecho de lo que permite el propio p-valor, y ambos se contradicen.
    """
    objetivo = 1.0 - conf
    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if p_two_sided(mid, df) > objetivo:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def cohen_d(a: list[float], b: list[float]) -> float:
    na, nb = len(a), len(b)
    sp = math.sqrt(((na - 1) * st.variance(a) + (nb - 1) * st.variance(b)) / (na + nb - 2))
    return (st.mean(b) - st.mean(a)) / sp


def describe(nombre: str, v: list[float]):
    print(
        f"{nombre:22} n={len(v)}  media={st.mean(v):.4f}  sd={st.stdev(v):.4f}  "
        f"min={min(v):.4f}  max={max(v):.4f}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--control", nargs="+", type=float, required=True)
    ap.add_argument("--tratamiento", nargs="+", type=float, required=True)
    ap.add_argument("--etiqueta", default="tratamiento")
    ap.add_argument("--alpha", type=float, default=0.05)
    args = ap.parse_args()

    if len(args.control) < 2 or len(args.tratamiento) < 2:
        raise SystemExit("Se necesitan al menos 2 ejecuciones por grupo para estimar la varianza")

    describe("control", args.control)
    describe(args.etiqueta, args.tratamiento)

    dif = st.mean(args.tratamiento) - st.mean(args.control)
    t, df, se = welch(args.control, args.tratamiento)
    p = p_two_sided(t, df)
    d = cohen_d(args.control, args.tratamiento)
    tc = t_critico(df, 1.0 - args.alpha)
    ic = tc * se

    print(f"\ndiferencia de medias  {dif:+.4f}  ({dif * 100:+.2f} pp)")
    print(
        f"IC {1 - args.alpha:.0%}              [{(dif - ic) * 100:+.2f}, {(dif + ic) * 100:+.2f}] pp"
        f"   (t critico {tc:.2f})"
    )
    print(f"t de Welch            {t:.2f}   gl={df:.1f}   p={p:.3f}")
    print(f"d de Cohen            {d:.2f}")
    if p < args.alpha:
        print(f"\n→ Diferencia significativa al {args.alpha:.0%}.")
    else:
        print(
            f"\n→ NO significativa al {args.alpha:.0%}: con estos tamaños de muestra la diferencia "
            "no se distingue del ruido entre semillas."
        )


if __name__ == "__main__":
    main()
