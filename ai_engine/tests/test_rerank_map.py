"""
Tests de las transformaciones y métricas de rerank_map.py.
Numpy puro: no cargan pesos del modelo ni spaCy.
"""

import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import average_precision_score

sys.path.insert(0, str(Path(__file__).parent.parent))

import baseline_dict as baseline_dict_module
from rerank_map import (
    _ap,
    build_gold,
    calibrate,
    dict_bonus_matrix,
    load_split,
    map_scores,
    map_strict_sklearn,
    probs_for,
    to_logits,
)

# =============================================================================
# _ap: debe coincidir con sklearn, que es la referencia usada en eval_test.py
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
# build_gold: el gold fuera de vocabulario cuenta en n_total pero no en n_reach
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


def test_map_strict_sklearn_coincide_con_la_version_rapida():
    c2i = {"A01": 0, "B02": 1}
    T, n_total, n_reach = build_gold([["A01", "Z99"], ["B02"]], c2i, 2)
    S = np.array([[9.0, 1.0], [2.0, 8.0]])
    _, strict = map_scores(T, S, n_total, n_reach)
    assert map_strict_sklearn(T, S, n_total, n_reach) == pytest.approx(strict)


def test_map_strict_sklearn_ignora_documentos_sin_gold():
    c2i = {"A01": 0}
    T, n_total, n_reach = build_gold([["A01"], []], c2i, 1)
    assert map_strict_sklearn(T, np.array([[3.0], [3.0]]), n_total, n_reach) == pytest.approx(1.0)


def test_calibrar_con_gamma_reescala_por_desviacion_tipica():
    z = np.array([[4.0, 4.0]])
    mu = np.array([0.0, 0.0])
    sigma = np.array([2.0, 4.0])
    resultado = calibrate(z, mu, sigma, lam=0.0, gamma=1.0)
    assert resultado[0, 0] == pytest.approx(2.0)  # 4 / 2
    assert resultado[0, 1] == pytest.approx(1.0)  # 4 / 4


def test_load_split_reutiliza_parse_labels_de_train(tmp_path):
    csv = tmp_path / "split.csv"
    csv.write_text("text,labels\nnota uno,A01.0;B02\nnota dos,C03\n", encoding="utf-8")
    textos, gold = load_split(str(csv))
    assert textos == ["nota uno", "nota dos"]
    assert gold == [["A01.0", "B02"], ["C03"]]  # full=True: no se trunca a bloque


def test_probs_for_usa_la_cache_si_ya_existe(tmp_path):
    cache_dir = tmp_path
    args = types.SimpleNamespace(label="prueba")
    np.save(cache_dir / "prueba_val.npy", np.array([[0.5, 0.5]]))
    with open(cache_dir / "prueba_code_to_idx.json", "w") as f:
        json.dump({"A01": 0, "B02": 1}, f)

    probs, c2i = probs_for("val", ["texto"], args, cache_dir)
    assert probs.tolist() == [[0.5, 0.5]]
    assert c2i == {"A01": 0, "B02": 1}


class TestDictBonusMatrix:
    def test_usa_la_cache_si_ya_existe(self, tmp_path):
        cache_path = tmp_path / "dict_val.npy"
        np.save(cache_path, np.array([[1.0, 0.0]]))
        resultado = dict_bonus_matrix(["texto"], "no_se_lee.json", ["A01", "B02"], cache_path)
        assert resultado.tolist() == [[1.0, 0.0]]

    def test_reparte_la_confianza_a_todos_los_codigos_del_bloque(self, tmp_path, monkeypatch):
        class DictClassifierFalso:
            def __init__(self, path):
                pass

            def predict(self, text):
                return [{"code": "A01", "confidence": 0.8}]

        monkeypatch.setattr(baseline_dict_module, "DictClassifier", DictClassifierFalso)
        cache_path = tmp_path / "dict_val.npy"
        resultado = dict_bonus_matrix(
            ["texto con hipertension"], "patrones.json", ["A01.0", "A01.9", "B02"], cache_path
        )
        assert np.allclose(resultado, [[0.8, 0.8, 0.0]], atol=1e-6)
        assert cache_path.exists()  # se guarda para no repetir el diccionario
