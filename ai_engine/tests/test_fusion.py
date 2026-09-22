"""
Tests de la fusión BERT + diccionario: vector de bonificación y explicabilidad.
Lógica pura: no cargan el modelo ni spaCy.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import _dict_bonus_vector, _triggers_fusion

C2I = {"A15.0": 0, "A15.9": 1, "J18.9": 2, "E11.9": 3}


# =============================================================================
# Vector de bonificación
# =============================================================================


def test_bonifica_todos_los_codigos_del_bloque_detectado():
    bonus, n = _dict_bonus_vector([{"code": "A15", "confidence": 0.8}], C2I, 6.0)
    assert n == 1
    assert bonus[0] == pytest.approx(4.8)  # A15.0
    assert bonus[1] == pytest.approx(4.8)  # A15.9
    assert bonus[2] == 0.0  # J18.9 no pertenece al bloque
    assert bonus[3] == 0.0


def test_sin_deteccion_el_vector_es_cero():
    bonus, n = _dict_bonus_vector([], C2I, 6.0)
    assert n == 0
    assert not bonus.any()


def test_varios_bloques_se_bonifican_a_la_vez():
    bonus, n = _dict_bonus_vector(
        [{"code": "A15", "confidence": 0.5}, {"code": "J18", "confidence": 1.0}], C2I, 2.0
    )
    assert n == 2
    assert bonus[0] == pytest.approx(1.0)
    assert bonus[2] == pytest.approx(2.0)


def test_bloque_repetido_se_queda_con_la_confianza_mayor():
    bonus, _ = _dict_bonus_vector(
        [{"code": "A15", "confidence": 0.3}, {"code": "A15", "confidence": 0.9}], C2I, 1.0
    )
    assert bonus[0] == pytest.approx(0.9)


def test_confianza_negativa_no_penaliza():
    bonus, _ = _dict_bonus_vector([{"code": "A15", "confidence": -2.0}], C2I, 1.0)
    assert bonus[0] == 0.0


def test_bloque_fuera_del_vocabulario_se_ignora():
    bonus, n = _dict_bonus_vector([{"code": "Z99", "confidence": 1.0}], C2I, 6.0)
    assert n == 1  # se detectó
    assert not bonus.any()  # pero ningún código del modelo pertenece a ese bloque


def test_beta_escala_la_bonificacion():
    b1, _ = _dict_bonus_vector([{"code": "A15", "confidence": 1.0}], C2I, 1.0)
    b6, _ = _dict_bonus_vector([{"code": "A15", "confidence": 1.0}], C2I, 6.0)
    assert b6[0] == pytest.approx(6.0 * b1[0])


def test_el_vector_tiene_el_tamano_del_espacio_de_codigos():
    bonus, _ = _dict_bonus_vector([{"code": "A15", "confidence": 1.0}], C2I, 6.0)
    assert bonus.shape == (len(C2I),)
    assert bonus.dtype == np.float32


# =============================================================================
# Explicabilidad
# =============================================================================

EXPLICA = {0: [("tuberculosis", 0.6), ("pulmonar", 0.4)]}
DICC = {"A15": ["mycobacterium tuberculosis", "baciloscopia positiva"]}


def test_los_terminos_del_diccionario_van_primero():
    pred = {"code": "A15.0", "dict_bonus": 4.8}
    assert _triggers_fusion(pred, EXPLICA, DICC, C2I)[0] == "mycobacterium tuberculosis"


def test_sin_respaldo_del_diccionario_solo_aparecen_los_del_modelo():
    pred = {"code": "A15.0", "dict_bonus": 0.0}
    assert _triggers_fusion(pred, EXPLICA, DICC, C2I) == ["tuberculosis", "pulmonar"]


def test_no_se_repiten_terminos_iguales():
    pred = {"code": "A15.0", "dict_bonus": 1.0}
    salida = _triggers_fusion(pred, {0: [("Tuberculosis", 0.5)]}, {"A15": ["tuberculosis"]}, C2I)
    assert salida == ["tuberculosis"]


def test_se_devuelven_como_mucho_cinco():
    pred = {"code": "A15.0", "dict_bonus": 1.0}
    explica = {0: [(f"palabra{i}", 0.1) for i in range(9)]}
    dicc = {"A15": [f"frase{i}" for i in range(4)]}
    assert len(_triggers_fusion(pred, explica, dicc, C2I)) == 5


def test_el_detalle_etiqueta_el_origen_de_cada_termino():
    pred = {"code": "A15.0", "dict_bonus": 4.8}
    detalle = _triggers_fusion(pred, EXPLICA, DICC, C2I, detallado=True)
    assert [d["source"] for d in detalle[:2]] == ["dict", "dict"]
    bert = [d for d in detalle if d["source"] == "bert"]
    assert bert and bert[0]["weight"] == pytest.approx(0.6)


def test_los_pesos_del_diccionario_no_se_inventan():
    # No comparten escala con los del modelo: se dejan a None en vez de fabricar un número
    pred = {"code": "A15.0", "dict_bonus": 4.8}
    detalle = _triggers_fusion(pred, EXPLICA, DICC, C2I, detallado=True)
    assert all(d["weight"] is None for d in detalle if d["source"] == "dict")


def test_codigo_desconocido_no_revienta():
    assert _triggers_fusion({"code": "X99.9", "dict_bonus": 0.0}, EXPLICA, DICC, C2I) == []
