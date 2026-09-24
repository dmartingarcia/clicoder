"""Latencia de proponer códigos, que es lo que fija el requisito de latencia.

Mide solo la predicción, sin atribución: son dos costes de orden distinto y el sistema los
sirve en peticiones separadas, de modo que mezclarlos no describe ninguna espera real. El
coste de explicar lo mide `bench_explain.py`.

Uso: python bench_predict.py [--device cpu|cuda] [--n 30]
"""

import argparse
import statistics
import time

import pandas as pd


def main():
    from classifier import CIE10Classifier

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="cpu", help="cpu | cuda")
    ap.add_argument("--n", type=int, default=30, help="Informes a medir.")
    ap.add_argument("--test_file", default="/data/codiesp_csvs/codiesp_D_source_test.csv")
    args = ap.parse_args()

    clf = CIE10Classifier("/app/model", device=args.device)
    d = pd.read_csv(args.test_file)
    d.columns = d.columns.str.strip()
    textos = d.dropna(subset=["text"])["text"].astype(str).tolist()[: args.n]

    # La primera pasada no mide lo mismo que las siguientes: paga la reserva de memoria del
    # backend de torch y, en GPU, la creacion del contexto y la eleccion de kernels. Se informa
    # aparte en lugar de descartarla en silencio, que es lo unico que significa "calentar".
    t0 = time.perf_counter()
    clf.predict(textos[0], top_k=5)
    fria = time.perf_counter() - t0

    tiempos = []
    for texto in textos:
        t0 = time.perf_counter()
        clf.predict(texto, top_k=5)
        tiempos.append(time.perf_counter() - t0)

    tiempos.sort()
    print(f"device={args.device} informes={len(tiempos)} version={clf.version}")
    print(f"  primera  {fria:.3f} s (sin calentar)")
    print(f"  mediana  {statistics.median(tiempos):.3f} s")
    print(f"  media    {statistics.fmean(tiempos):.3f} s")
    print(f"  p95      {tiempos[int(0.95 * (len(tiempos) - 1))]:.3f} s")
    print(f"  min/max  {tiempos[0]:.3f} / {tiempos[-1]:.3f} s")


if __name__ == "__main__":
    main()
