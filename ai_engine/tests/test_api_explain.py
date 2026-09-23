"""
Tests de los endpoints añadidos al motor: explicabilidad separada, fusión y catálogo.

Usan dobles del clasificador y del diccionario, así que no hacen falta los pesos del modelo.
Lo que se comprueba es el contrato: qué devuelve cada endpoint y cómo se comporta cuando
falta una pieza, que es donde un cliente se rompe sin mensaje útil.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import main as main_module


@pytest.fixture
def cliente_sin_modelo(tmp_path):
    anterior = os.environ.get("MODEL_DIR")
    os.environ["MODEL_DIR"] = str(tmp_path / "no-existe")
    with TestClient(main_module.app) as cliente:
        main_module.classifier = None
        main_module.dict_classifier = None
        yield cliente
    main_module.classifier = None
    main_module.dict_classifier = None
    if anterior:
        os.environ["MODEL_DIR"] = anterior


@pytest.fixture
def cliente_completo(tmp_path):
    """Cliente con clasificador y diccionario simulados, y un catálogo en disco."""
    import json

    (tmp_path / "models.json").write_text(
        json.dumps(
            {
                "repo": "ejemplo/repo",
                "nota_medicion": "prueba",
                "modelos": {
                    "produccion": {
                        "checkpoint": "classifier.pt",
                        "thresholds": "thresholds.json",
                        "descripcion": "el de siempre",
                        "umbral": 0.3,
                        "fusion_threshold": 2.9,
                        "comparables": {"map_test": 0.43, "f1_micro_test": 0.48},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "classifier.pt").write_bytes(b"x")

    anterior = os.environ.get("MODEL_DIR")
    os.environ["MODEL_DIR"] = str(tmp_path)

    clf = MagicMock()
    clf.code_to_idx = {"I10": 0, "E11.9": 1}
    clf.config = {"fusion_beta": 6.0, "fusion_threshold": 2.9, "model_file": "classifier.pt"}
    clf.explain.return_value = {0: [("hipertensión", 0.7), ("arterial", 0.3)]}
    clf.predict.return_value = [
        {"code": "I10", "probability": 0.9, "chapter": "IX", "chapter_name": "Circulatorio"}
    ]

    dic = MagicMock()
    dic.predict.return_value = [
        {"code": "I10", "confidence": 0.95, "matched_terms": ["hipertension arterial"]}
    ]

    with TestClient(main_module.app) as cliente:
        main_module.classifier = clf
        main_module.dict_classifier = dic
        main_module.code_descriptions = {"I10": "Hipertensión esencial"}
        yield cliente

    main_module.classifier = None
    main_module.dict_classifier = None
    if anterior:
        os.environ["MODEL_DIR"] = anterior


# =============================================================================
# /explain
# =============================================================================


class TestExplain:
    def test_sin_modelo_devuelve_503(self, cliente_sin_modelo):
        r = cliente_sin_modelo.post("/explain", json={"text": "hola", "codes": ["I10"]})
        assert r.status_code == 503

    def test_texto_vacio_es_error_de_validacion(self, cliente_completo):
        assert (
            cliente_completo.post("/explain", json={"text": "  ", "codes": ["I10"]}).status_code
            == 422
        )

    def test_metodo_desconocido_lista_los_disponibles(self, cliente_completo):
        r = cliente_completo.post(
            "/explain", json={"text": "hola", "codes": ["I10"], "method": "magia"}
        )
        assert r.status_code == 422
        assert "gradiente_filtrado" in r.json()["detail"]["disponibles"]

    def test_devuelve_los_terminos_con_su_peso(self, cliente_completo):
        r = cliente_completo.post(
            "/explain", json={"text": "paciente hipertenso", "codes": ["I10"]}
        )
        assert r.status_code == 200
        terminos = r.json()["triggers"]["I10"]
        assert terminos[0]["term"] == "hipertensión"
        assert terminos[0]["weight"] == 0.7

    def test_informa_del_metodo_empleado(self, cliente_completo):
        """Sin este dato no se puede saber después si un término raro vino de la versión
        fiel o de una rápida."""
        r = cliente_completo.post("/explain", json={"text": "hola", "codes": ["I10"]})
        assert r.json()["method"]

    def test_los_codigos_desconocidos_se_reportan_aparte(self, cliente_completo):
        r = cliente_completo.post("/explain", json={"text": "hola", "codes": ["I10", "ZZZ"]})
        assert r.json()["unknown_codes"] == ["ZZZ"]

    def test_el_metodo_diccionario_no_usa_el_encoder(self, cliente_completo):
        r = cliente_completo.post(
            "/explain",
            json={"text": "hipertension arterial", "codes": ["I10"], "method": "diccionario"},
        )
        assert r.status_code == 200
        assert r.json()["method"] == "diccionario"
        assert r.json()["triggers"]["I10"][0]["term"] == "hipertension arterial"

    def test_el_diccionario_no_inventa_peso(self, cliente_completo):
        """Su confianza no comparte escala con la importancia del modelo, así que se deja
        vacía en lugar de fabricar un número comparable."""
        r = cliente_completo.post(
            "/explain", json={"text": "hipertension", "codes": ["I10"], "method": "diccionario"}
        )
        assert r.json()["triggers"]["I10"][0]["weight"] is None


# =============================================================================
# /admin/models
# =============================================================================


class TestCatalogoModelos:
    def test_lista_los_modelos_del_catalogo(self, cliente_completo):
        r = cliente_completo.get("/admin/models")
        assert r.status_code == 200
        assert [m["name"] for m in r.json()["models"]] == ["produccion"]

    def test_indica_si_estan_descargados(self, cliente_completo):
        assert cliente_completo.get("/admin/models").json()["models"][0]["downloaded"] is True

    def test_indica_cual_esta_cargado(self, cliente_completo):
        assert cliente_completo.get("/admin/models").json()["models"][0]["loaded"] is True

    def test_incluye_las_metricas_para_poder_elegir(self, cliente_completo):
        metricas = cliente_completo.get("/admin/models").json()["models"][0]["metrics"]
        assert "map_test" in metricas

    def test_un_modelo_desconocido_devuelve_los_disponibles(self, cliente_completo):
        r = cliente_completo.post("/admin/models", json={"name": "inventado"})
        assert r.status_code == 422
        assert "produccion" in r.json()["detail"]["disponibles"]

    def test_sin_catalogo_la_lista_va_vacia(self, cliente_sin_modelo):
        assert cliente_sin_modelo.get("/admin/models").json()["models"] == []


# =============================================================================
# Predicción con términos diferidos
# =============================================================================


class TestPrediccionDiferida:
    def test_por_defecto_no_calcula_los_terminos(self, cliente_completo):
        """La atribución cuesta dos órdenes de magnitud más: se pide aparte."""
        r = cliente_completo.post("/predict", json={"text": "paciente hipertenso"})
        assert r.status_code == 200
        codigo = r.json()["cards"][0]["content"][0]
        assert codigo["triggers_complete"] is False

    def test_se_pueden_pedir_en_la_misma_llamada(self, cliente_completo):
        r = cliente_completo.post(
            "/predict", json={"text": "paciente hipertenso", "include_triggers": True}
        )
        assert r.json()["cards"][0]["content"][0]["triggers_complete"] is True
