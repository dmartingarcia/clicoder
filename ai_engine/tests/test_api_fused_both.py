"""
Tests de los modos engine=fused y engine=both de /predict, y de las ramas de
error que quedaban sin ejercitar en /explain, el lifespan y los jobs.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import main as main_module
import summarizer as summarizer_module


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))

    clf = MagicMock()
    clf.code_to_idx = {"I10": 0, "J45": 1}
    clf.config = {"fusion_beta": 6.0, "fusion_threshold": 2.9}
    clf.predict.return_value = [
        {
            "code": "I10",
            "probability": 0.9,
            "chapter": "IX",
            "chapter_name": "Circulatorio",
            "score": 5.0,
            "dict_bonus": 4.8,
        }
    ]
    clf.explain.return_value = {}

    dic = MagicMock()
    dic.predict.return_value = [
        {"code": "I10", "confidence": 0.95, "matched_terms": ["hipertension"]}
    ]

    with TestClient(main_module.app) as client:
        main_module.classifier = clf
        main_module.dict_classifier = dic
        main_module.summarizer = None
        main_module.code_descriptions = {"I10": "Hipertensión esencial"}
        yield client

    main_module.classifier = None
    main_module.dict_classifier = None
    main_module.summarizer = None
    main_module._jobs.clear()


class TestPredictFused:
    def test_sin_diccionario_es_un_503(self, cliente):
        main_module.dict_classifier = None
        r = cliente.post("/predict", json={"text": "texto", "engine": "fused"})
        assert r.status_code == 503

    def test_sin_bert_es_un_503(self, cliente):
        main_module.classifier = None
        r = cliente.post("/predict", json={"text": "texto", "engine": "fused"})
        assert r.status_code == 503

    def test_devuelve_el_reparto_de_puntuacion_por_fuente(self, cliente):
        r = cliente.post("/predict", json={"text": "texto con hipertension", "engine": "fused"})
        assert r.status_code == 200
        entrada = r.json()["cards"][0]["content"][0]
        assert entrada["score_dict"] == pytest.approx(4.8)
        assert entrada["dict_support"] is True

    def test_pasa_el_umbral_y_beta_de_la_config_al_clasificador(self, cliente):
        cliente.post("/predict", json={"text": "texto", "engine": "fused"})
        args = main_module.classifier.predict.call_args[0]
        assert args[-1] == pytest.approx(2.9)

    def test_con_include_triggers_pide_la_explicacion_al_modelo(self, cliente):
        cliente.post(
            "/predict", json={"text": "texto", "engine": "fused", "include_triggers": True}
        )
        main_module.classifier.explain.assert_called_once()

    def test_sin_include_triggers_no_toca_el_encoder(self, cliente):
        cliente.post("/predict", json={"text": "texto", "engine": "fused"})
        main_module.classifier.explain.assert_not_called()


class TestPredictBoth:
    def test_junta_los_codigos_de_los_dos_motores(self, cliente):
        r = cliente.post("/predict", json={"text": "texto con hipertension", "engine": "both"})
        assert r.status_code == 200
        motores = {c["engine"] for c in r.json()["cards"][0]["content"]}
        assert motores == {"bert", "dict"}

    def test_no_deduplica_un_codigo_visto_por_los_dos(self, cliente):
        r = cliente.post("/predict", json={"text": "texto con hipertension", "engine": "both"})
        codigos = [c["code"] for c in r.json()["cards"][0]["content"]]
        assert codigos.count("I10") == 2

    def test_reporta_el_tiempo_de_cada_motor_por_separado(self, cliente):
        r = cliente.post("/predict", json={"text": "texto", "engine": "both"})
        timing = r.json()["timing"]
        assert "bert_classifier_ms" in timing
        assert "dict_classifier_ms" in timing


def test_explain_diccionario_sin_diccionario_cargado_es_503(cliente):
    main_module.dict_classifier = None
    r = cliente.post("/explain", json={"text": "texto", "codes": ["I10"], "method": "diccionario"})
    assert r.status_code == 503


def _esperar(client, job_id, intentos=20):
    import time

    for _ in range(intentos):
        r = client.get(f"/jobs/{job_id}")
        if r.json()["status"] != "pending":
            return r
        time.sleep(0.02)
    raise AssertionError("el job no terminó a tiempo")


def test_job_predict_engine_both(cliente):
    job_id = cliente.post(
        "/jobs/predict", json={"text": "texto con hipertension", "engine": "both"}
    ).json()["job_id"]
    r = _esperar(cliente, job_id)
    assert r.json()["status"] == "done"
    motores = {c["engine"] for c in r.json()["result"]["cards"][0]["content"]}
    assert motores == {"bert", "dict"}


def test_job_predict_guarda_el_detalle_de_un_httpexception_no_textual(cliente):
    """El detail es un dict (error + solución), no una cadena: el job debe convertirlo a texto."""
    main_module.dict_classifier = None
    job_id = cliente.post("/jobs/predict", json={"text": "texto", "engine": "dict"}).json()[
        "job_id"
    ]
    r = _esperar(cliente, job_id)
    assert r.json()["status"] == "error"
    assert "diccionario" in r.json()["error"].lower()


def test_job_predict_con_un_error_no_http_tambien_queda_en_error(cliente):
    """Sin HTTPException no hay detail: str(exc) es lo único disponible."""
    main_module.classifier.predict.side_effect = RuntimeError("fallo inesperado del modelo")
    job_id = cliente.post("/jobs/predict", json={"text": "texto"}).json()["job_id"]
    r = _esperar(cliente, job_id)
    assert r.json()["status"] == "error"
    assert "fallo inesperado del modelo" in r.json()["error"]


def test_job_summarize_con_fallo_del_summarizer_queda_en_error(cliente):
    resumidor = MagicMock()
    resumidor.summarize.side_effect = RuntimeError("fallo del LLM")
    main_module.summarizer = resumidor
    job_id = cliente.post("/jobs/summarize", json={"text": "texto"}).json()["job_id"]
    r = _esperar(cliente, job_id)
    assert r.json()["status"] == "error"
    assert "fallo del LLM" in r.json()["error"]


def test_un_fallo_al_inicializar_el_summarizer_no_impide_arrancar(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_DIR", str(tmp_path / "no-existe"))
    monkeypatch.setenv("SUMMARIZER_MODEL", "gemma3")

    class ResumidorQueFallaAlCargar:
        def load(self):
            raise RuntimeError("GGUF corrupto")

    monkeypatch.setattr(summarizer_module, "create_summarizer", lambda: ResumidorQueFallaAlCargar())

    with TestClient(main_module.app):
        assert main_module.summarizer is None


def test_un_cuerpo_no_json_en_predict_no_rompe_el_logging(cliente):
    r = cliente.post(
        "/predict", content=b"esto no es json", headers={"content-type": "application/json"}
    )
    assert r.status_code == 422  # FastAPI rechaza el body, pero el middleware no revienta antes


class TestMotorPorDefecto:
    """Sin ``engine`` se usa el motor de mejor MAP disponible."""

    def test_es_fused_si_estan_el_modelo_y_el_diccionario(self, monkeypatch):
        monkeypatch.setattr(main_module, "classifier", object())
        monkeypatch.setattr(main_module, "dict_classifier", object())
        assert main_module._motor_efectivo(main_module.AnalysisRequest(text="x")) == "fused"

    def test_cae_a_bert_si_falta_el_diccionario(self, monkeypatch):
        monkeypatch.setattr(main_module, "classifier", object())
        monkeypatch.setattr(main_module, "dict_classifier", None)
        assert main_module._motor_efectivo(main_module.AnalysisRequest(text="x")) == "bert"

    def test_respeta_el_motor_pedido(self, monkeypatch):
        monkeypatch.setattr(main_module, "classifier", object())
        monkeypatch.setattr(main_module, "dict_classifier", object())
        peticion = main_module.AnalysisRequest(text="x", engine="dict")
        assert main_module._motor_efectivo(peticion) == "dict"
