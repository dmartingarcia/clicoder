"""
Tests de las transformaciones y métricas de rerank_map.py.
Numpy puro: no cargan pesos del modelo ni spaCy.
"""

import sys
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import average_precision_score

sys.path.insert(0, str(Path(__file__).parent.parent))

from rerank_map import _ap, build_gold, calibrate, map_scores, to_logits

# =============================================================================
# _ap — debe coincidir con sklearn, que es la referencia usada en eval_test.py
# =============================================================================


def test_ap_coincide_con_sklearn():
    rng = np.random.default_rng(0)
    for _ in range(20):
        scores = rng.normal(size=200)
        target = (rng.random(200) < 0.05).astype(np.int8)
        if target.sum() == 0:
            continue
        assert _ap(scores, target) == pytest.approx(
            average_precision_score(target, scores), abs=1e-9
        )


def test_ap_ranking_perfecto_es_uno():
    scores = np.array([9.0, 8.0, 1.0, 0.5])
    target = np.array([1, 1, 0, 0], dtype=np.int8)
    assert _ap(scores, target) == pytest.approx(1.0)


def test_ap_sin_positivos_es_cero():
    assert _ap(np.array([1.0, 2.0]), np.zeros(2, dtype=np.int8)) == 0.0


# =============================================================================
# to_logits / calibrate
# =============================================================================


def test_to_logits_es_monotona():
    p = np.array([[0.01, 0.2, 0.5, 0.9]])
    z = to_logits(p)
    assert np.all(np.diff(z[0]) > 0)
    assert z[0][2] == pytest.approx(0.0, abs=1e-9)


def test_to_logits_recorta_extremos_sin_infinitos():
    z = to_logits(np.array([[0.0, 1.0]]))
    assert np.all(np.isfinite(z))


def test_calibrar_con_lambda_gamma_cero_no_cambia_nada():
    rng = np.random.default_rng(1)
    z = rng.normal(size=(5, 7))
    mu, sigma = z.mean(axis=0), z.std(axis=0)
    assert np.allclose(calibrate(z, mu, sigma, 0.0, 0.0), z)


def test_calibrar_reordena_dentro_del_documento():
    # Clase 0 alta en todos los documentos (sesgo de frecuencia), clase 1 alta
    # solo en este documento: tras centrar, la clase 1 debe adelantar a la 0.
    z_train = np.array([[5.0, -5.0], [5.0, -5.0], [5.0, -5.0]])
    mu, sigma = z_train.mean(axis=0), z_train.std(axis=0)
    doc = np.array([[5.0, 0.0]])
    assert np.argmax(doc[0]) == 0
    assert np.argmax(calibrate(doc, mu, sigma, 1.0, 0.0)[0]) == 1


# =============================================================================
# build_gold — el gold fuera de vocabulario cuenta en n_total pero no en n_reach
# =============================================================================


def test_build_gold_separa_alcanzable_de_total():
    c2i = {"A01": 0, "B02": 1}
    T, n_total, n_reach = build_gold([["A01", "Z99"], [], ["B02", "B02"]], c2i, 2)
    assert T.tolist() == [[1, 0], [0, 0], [0, 1]]
    assert n_total.tolist() == [2, 0, 1]
    assert n_reach.tolist() == [1, 0, 1]


def test_map_estricto_penaliza_el_gold_fuera_de_vocabulario():
    c2i = {"A01": 0, "B02": 1}
    gold = [["A01", "Z99"]]  # la mitad del gold es inalcanzable
    T, n_total, n_reach = build_gold(gold, c2i, 2)
    S = np.array([[9.0, 1.0]])  # ranking perfecto sobre lo alcanzable
    reach, strict = map_scores(T, S, n_total, n_reach)
    assert reach == pytest.approx(1.0)
    assert strict == pytest.approx(0.5)


def test_map_ignora_documentos_sin_gold():
    c2i = {"A01": 0}
    T, n_total, n_reach = build_gold([["A01"], []], c2i, 1)
    reach, strict = map_scores(T, np.array([[3.0], [3.0]]), n_total, n_reach)
    assert reach == pytest.approx(1.0)
    assert strict == pytest.approx(1.0)
