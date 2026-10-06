"""
Tests del contraste estadístico de compare_runs.py.
El p-valor acaba en la memoria del TFG, así que se contrasta contra tablas de la t de Student.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import compare_runs
from compare_runs import cohen_d, describe, p_two_sided, t_critico, welch

# (t, grados de libertad, p bilateral según tablas)
TABLA_T = [
    (2.0, 10, 0.0734),
    (1.0, 1, 0.5000),
    (2.228, 10, 0.0500),
    (3.182, 3, 0.0500),
    (1.6, 7, 0.1538),
    (0.0, 5, 1.0000),
]


@pytest.mark.parametrize(("t", "df", "esperado"), TABLA_T)
def test_p_bilateral_coincide_con_las_tablas(t, df, esperado):
    assert p_two_sided(t, df) == pytest.approx(esperado, abs=2e-3)


def test_p_es_simetrico_en_el_signo_de_t():
    assert p_two_sided(2.3, 6) == pytest.approx(p_two_sided(-2.3, 6), abs=1e-12)


def test_p_decrece_al_crecer_t():
    ps = [p_two_sided(t, 8) for t in (0.5, 1.0, 2.0, 4.0)]
    assert ps == sorted(ps, reverse=True)


def test_welch_detecta_grupos_identicos():
    a = [0.43, 0.44, 0.42]
    t, df, se = welch(a, list(a))
    assert t == pytest.approx(0.0, abs=1e-12)
    assert se > 0


def test_welch_signo_positivo_si_el_tratamiento_es_mayor():
    t, _, _ = welch([0.42, 0.43, 0.44], [0.45, 0.46, 0.47])
    assert t > 0


def test_cohen_d_escala_con_la_separacion():
    base = [0.42, 0.43, 0.44]
    poco = cohen_d(base, [0.43, 0.44, 0.45])
    mucho = cohen_d(base, [0.50, 0.51, 0.52])
    assert 0 < poco < mucho


# Cuantil t: con pocos grados de libertad se separa mucho de la normal, y usar
# 1,96 produce intervalos incompatibles con su propio p-valor.


@pytest.mark.parametrize(
    ("df", "esperado"),
    [(1, 12.706), (3, 3.182), (5, 2.571), (10, 2.228), (30, 2.042), (1000, 1.962)],
)
def test_t_critico_coincide_con_las_tablas(df, esperado):
    assert t_critico(df) == pytest.approx(esperado, abs=5e-3)


def test_t_critico_decrece_hacia_la_normal():
    valores = [t_critico(df) for df in (2, 5, 20, 200, 5000)]
    assert valores == sorted(valores, reverse=True)
    # Con muchos grados de libertad converge al 1,96 de la normal, pero solo en el límite:
    # con 200 todavía vale 1,972, que es justo por lo que no sirve para n pequeños.
    assert valores[-1] == pytest.approx(1.96, abs=0.005)
    assert valores[-2] > 1.97


def test_p_bilateral_con_t_extremo_no_desborda():
    # t*t desborda a infinito en float64: x = df/(df+inf) cae exactamente a 0.
    assert p_two_sided(1e200, 5) == pytest.approx(0.0, abs=1e-12)


def test_describe_informa_de_n_media_y_rango(capsys):
    describe("control", [0.42, 0.44, 0.43])
    salida = capsys.readouterr().out
    assert "n=3" in salida
    assert "media=" in salida


def _argv(control, tratamiento, extra=()):
    return [
        "compare_runs.py",
        "--control",
        *[str(v) for v in control],
        "--tratamiento",
        *[str(v) for v in tratamiento],
        *extra,
    ]


class TestMain:
    def test_menos_de_dos_ejecuciones_por_grupo_es_un_error_de_uso(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", _argv([0.4], [0.4, 0.5]))
        with pytest.raises(SystemExit):
            compare_runs.main()

    def test_diferencia_significativa_se_anuncia_como_tal(self, monkeypatch, capsys):
        control = [0.4315, 0.4317, 0.4421, 0.4335, 0.4406]
        tratamiento = [0.4535, 0.4383, 0.4437, 0.4511]
        monkeypatch.setattr(sys, "argv", _argv(control, tratamiento))
        compare_runs.main()
        assert "Diferencia significativa" in capsys.readouterr().out

    def test_diferencia_no_significativa_se_anuncia_como_tal(self, monkeypatch, capsys):
        control = [0.43, 0.44]
        tratamiento = [0.431, 0.439]
        monkeypatch.setattr(sys, "argv", _argv(control, tratamiento))
        compare_runs.main()
        assert "NO significativa" in capsys.readouterr().out

    def test_la_etiqueta_del_tratamiento_aparece_en_la_salida(self, monkeypatch, capsys):
        monkeypatch.setattr(
            sys, "argv", _argv([0.43, 0.44], [0.45, 0.46], extra=["--etiqueta", "ZLPR+MAP"])
        )
        compare_runs.main()
        assert "ZLPR+MAP" in capsys.readouterr().out


def test_el_intervalo_es_coherente_con_el_contraste():
    # Si p < 0,05 el IC del 95 % no puede contener el cero, y viceversa.
    control, tratamiento = (
        [0.4315, 0.4317, 0.4421, 0.4335, 0.4406],
        [0.4535, 0.4383, 0.4437, 0.4511],
    )
    t, df, se = welch(control, tratamiento)
    import statistics as st

    dif = st.mean(tratamiento) - st.mean(control)
    ic_bajo = dif - t_critico(df) * se
    assert p_two_sided(t, df) < 0.05
    assert ic_bajo > 0
