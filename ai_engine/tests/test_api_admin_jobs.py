"""Tests de los endpoints de administración y de los jobs asíncronos."""

import asyncio
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import main as main_module
import summarizer as summarizer_module


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    """Catálogo con dos modelos: uno descargado (activo), otro que no está en disco."""
    (tmp_path / "models.json").write_text(
        json.dumps(
            {
                "modelos": {
                    "produccion": {
                        "checkpoint": "classifier.pt",
                        "thresholds": "thresholds.json",
                        "descripcion": "el de siempre",
                        "umbral": 0.3,
                        "fusion_threshold": 2.9,
                        "comparables": {"map_test": 0.43},
                    },
                    "sin_descargar": {
                        "checkpoint": "classifier-b.pt",
                        "thresholds": "thresholds-b.json",
                        "descripcion": "otro",
                        "umbral": 0.2,
                        "fusion_threshold": 2.0,
                        "comparables": {"map_test": 0.40},
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "classifier.pt").write_bytes(b"x")

    monkeypatch.setenv("MODEL_DIR", str(tmp_path))

    clf = MagicMock()
    clf.config = {"model_file": "classifier.pt"}
    clf.code_to_idx = {"I10": 0}
    clf.tokenizer = lambda text, **kw: {"input_ids": list(range(len(text.split()) + 2))}

    dic = MagicMock()

    with TestClient(main_module.app) as client:
        main_module.classifier = clf
        main_module.dict_classifier = dic
        main_module.summarizer = None
        main_module.code_descriptions = {}
        yield client, tmp_path

    main_module.classifier = None
    main_module.dict_classifier = None
    main_module.summarizer = None
    main_module._jobs.clear()


class TestAdminLoadModel:
    def test_modelo_no_descargado_devuelve_404_con_la_solucion(self, cliente):
        client, _ = cliente
        r = client.post("/admin/models", json={"name": "sin_descargar"})
        assert r.status_code == 404
        assert "model-download" in r.json()["detail"]["solucion"]

    def test_carga_correcta_sustituye_el_clasificador_activo(self, cliente, monkeypatch):
        client, _tmp_path = cliente
        nuevo = MagicMock()
        monkeypatch.setattr(
            "classifier.CIE10Classifier", lambda model_dir, device, overrides: nuevo
        )
        r = client.post("/admin/models", json={"name": "produccion"})
        assert r.status_code == 200
        assert r.json()["status"] == "loaded"
        assert main_module.classifier is nuevo

    def test_un_fallo_de_carga_no_toca_el_modelo_que_ya_servia(self, cliente, monkeypatch):
        """Si la carga falla, el clasificador que ya atendía peticiones no se toca."""
        client, _tmp_path = cliente
        anterior = main_module.classifier

        def revienta(model_dir, device, overrides):
            raise RuntimeError("checkpoint incompatible")

        monkeypatch.setattr("classifier.CIE10Classifier", revienta)
        r = client.post("/admin/models", json={"name": "produccion"})
        assert r.status_code == 500
        assert main_module.classifier is anterior

    def test_la_respuesta_incluye_el_tiempo_de_carga(self, cliente, monkeypatch):
        client, _tmp_path = cliente
        monkeypatch.setattr(
            "classifier.CIE10Classifier", lambda model_dir, device, overrides: MagicMock()
        )
        r = client.post("/admin/models", json={"name": "produccion"})
        assert r.json()["timing"]["load_ms"] >= 0


class FakeSummarizer:
    def __init__(self, model_key, mode, system_prompt, user_prompt):
        self._model_key = model_key
        self._mode = mode
        self.is_loaded = False
        self.prompts_actualizados = None

    def load(self):
        self.is_loaded = True

    def update_prompts(self, system_prompt, user_prompt):
        self.prompts_actualizados = (system_prompt, user_prompt)


class FakeSummarizerQueFalla(FakeSummarizer):
    def load(self):
        raise RuntimeError("modelo GGUF corrupto")


class TestAdminSummarizer:
    def test_modelo_desconocido_es_un_422(self, cliente):
        client, _ = cliente
        r = client.post("/admin/summarizer", json={"model": "modelo-inventado"})
        assert r.status_code == 422
        assert "ERR_INVALID_MODEL" in r.json()["detail"]

    def test_modo_desconocido_es_un_422(self, cliente):
        client, _ = cliente
        r = client.post("/admin/summarizer", json={"model": "none", "mode": "modo-raro"})
        assert r.status_code == 422
        assert "ERR_INVALID_MODE" in r.json()["detail"]

    def test_none_desactiva_el_resumidor(self, cliente):
        client, _ = cliente
        main_module.summarizer = FakeSummarizer("gemma3", "summary", "s", "u {text}")
        r = client.post("/admin/summarizer", json={"model": "none"})
        assert r.status_code == 200
        assert r.json()["status"] == "disabled"
        assert main_module.summarizer is None

    def test_mismo_modelo_y_modo_solo_actualiza_los_prompts(self, cliente, monkeypatch):
        client, _ = cliente
        actual = FakeSummarizer("gemma3", "summary", "s", "u {text}")
        actual.is_loaded = True
        main_module.summarizer = actual
        monkeypatch.setattr(summarizer_module, "MedicalSummarizer", FakeSummarizer)

        r = client.post(
            "/admin/summarizer",
            json={
                "model": "gemma3",
                "mode": "summary",
                "system_prompt": "Nuevo sistema",
                "user_prompt": "Nuevo {text}",
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "prompts_updated"
        assert actual.prompts_actualizados == ("Nuevo sistema", "Nuevo {text}")
        assert main_module.summarizer is actual

    def test_prompts_invalidos_al_actualizar_dan_422(self, cliente):
        """update_prompts() es el de verdad: su ValueError debe traducirse a 422, no a 500."""
        client, _ = cliente
        actual = summarizer_module.MedicalSummarizer("gemma3", "summary", "s", "u {text}")
        actual._llm = object()
        main_module.summarizer = actual
        r = client.post(
            "/admin/summarizer",
            json={"model": "gemma3", "mode": "summary", "system_prompt": "", "user_prompt": "x"},
        )
        assert r.status_code == 422

    def test_cambiar_de_modelo_carga_el_nuevo_antes_de_descartar_el_viejo(
        self, cliente, monkeypatch
    ):
        client, _ = cliente
        main_module.summarizer = None
        monkeypatch.setattr(summarizer_module, "MedicalSummarizer", FakeSummarizer)

        r = client.post(
            "/admin/summarizer",
            json={
                "model": "qwen",
                "mode": "summary",
                "system_prompt": "s",
                "user_prompt": "u {text}",
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "loaded"
        assert isinstance(main_module.summarizer, FakeSummarizer)
        assert main_module.summarizer.is_loaded is True

    def test_un_fallo_al_cargar_el_nuevo_modelo_es_un_500(self, cliente, monkeypatch):
        client, _ = cliente
        monkeypatch.setattr(summarizer_module, "MedicalSummarizer", FakeSummarizerQueFalla)

        r = client.post(
            "/admin/summarizer",
            json={
                "model": "qwen",
                "mode": "summary",
                "system_prompt": "s",
                "user_prompt": "u {text}",
            },
        )
        assert r.status_code == 500


class TestCountTokens:
    def test_sin_modelo_es_un_503(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MODEL_DIR", str(tmp_path / "no-existe"))
        with TestClient(main_module.app) as client:
            main_module.classifier = None
            r = client.post("/count-tokens", json={"text": "hola"})
        assert r.status_code == 503

    def test_cuenta_los_tokens_del_tokenizador(self, cliente):
        client, _ = cliente
        r = client.post("/count-tokens", json={"text": "una dos tres"})
        assert r.json()["token_count"] == 5


def _esperar_job(client, job_id, intentos=20):
    for _ in range(intentos):
        r = client.get(f"/jobs/{job_id}")
        if r.json()["status"] != "pending":
            return r
        time.sleep(0.02)
    raise AssertionError("el job no terminó a tiempo")


class TestJobsPredict:
    def test_job_desconocido_es_404(self, cliente):
        client, _ = cliente
        assert client.get("/jobs/no-existe").status_code == 404

    def test_texto_vacio_es_422(self, cliente):
        client, _ = cliente
        assert client.post("/jobs/predict", json={"text": "  "}).status_code == 422

    def test_devuelve_un_job_id_pendiente(self, cliente):
        client, _ = cliente
        r = client.post("/jobs/predict", json={"text": "paciente con hipertensión"})
        assert r.status_code == 200
        assert r.json()["status"] == "pending"
        assert r.json()["job_id"]

    def test_el_job_termina_en_done_con_el_resultado_de_predict(self, cliente):
        client, _ = cliente
        main_module.classifier.predict.return_value = [
            {"code": "I10", "probability": 0.9, "chapter": "IX", "chapter_name": "Circulatorio"}
        ]
        job_id = client.post("/jobs/predict", json={"text": "paciente con hipertensión"}).json()[
            "job_id"
        ]
        r = _esperar_job(client, job_id)
        assert r.json()["status"] == "done"
        assert r.json()["result"]["cards"][0]["content"][0]["code"] == "I10"

    def test_engine_dict_encola_la_prediccion_del_diccionario(self, cliente):
        client, _ = cliente
        main_module.dict_classifier.predict.return_value = [
            {"code": "I10", "confidence": 1.0, "matched_terms": ["hipertension"]}
        ]
        job_id = client.post(
            "/jobs/predict", json={"text": "hipertension", "engine": "dict"}
        ).json()["job_id"]
        r = _esperar_job(client, job_id)
        assert r.json()["result"]["cards"][0]["content"][0]["engine"] == "dict"

    def test_un_fallo_del_motor_deja_el_job_en_error(self, cliente):
        client, _ = cliente
        main_module.classifier = None  # fuerza el 503 interno de _predict_bert
        job_id = client.post("/jobs/predict", json={"text": "paciente"}).json()["job_id"]
        r = _esperar_job(client, job_id)
        assert r.json()["status"] == "error"
        assert r.json()["error"]


class TestJobsSummarize:
    def test_texto_vacio_es_422(self, cliente):
        client, _ = cliente
        assert client.post("/jobs/summarize", json={"text": ""}).status_code == 422

    def test_sin_summarizer_usa_el_resumen_estadistico(self, cliente):
        client, _ = cliente
        main_module.summarizer = None
        job_id = client.post("/jobs/summarize", json={"text": "una dos tres"}).json()["job_id"]
        r = _esperar_job(client, job_id)
        assert r.json()["status"] == "done"
        assert "3 palabras" in r.json()["result"]["text"]

    def test_con_summarizer_usa_su_resultado(self, cliente):
        client, _ = cliente
        resumidor = MagicMock()
        resumidor.summarize.return_value = "Resumen ya generado"
        main_module.summarizer = resumidor
        job_id = client.post("/jobs/summarize", json={"text": "informe largo"}).json()["job_id"]
        r = _esperar_job(client, job_id)
        assert r.json()["result"]["text"] == "Resumen ya generado"


class TestSummarizeStreamConLLM:
    def test_transmite_los_fragmentos_del_summarizer(self, cliente):
        client, _ = cliente

        class SummarizerDeMentira:
            def summarize_stream(self, text, system_prompt=None, user_prompt=None):
                yield "Hola "
                yield "mundo"

        main_module.summarizer = SummarizerDeMentira()
        r = client.post("/summarize/stream", json={"text": "informe de prueba"})
        assert r.status_code == 200
        lineas = [json.loads(ln) for ln in r.text.strip().splitlines() if ln]
        tokens = "".join(ln.get("token", "") for ln in lineas)
        assert tokens == "Hola mundo"
        assert lineas[-1] == {"done": True}

    def test_un_fallo_del_summarizer_se_reporta_y_aun_asi_cierra_el_stream(self, cliente):
        client, _ = cliente

        class SummarizerRoto:
            def summarize_stream(self, text, system_prompt=None, user_prompt=None):
                yield "empieza"
                raise RuntimeError("fallo a media generación")

        main_module.summarizer = SummarizerRoto()
        r = client.post("/summarize/stream", json={"text": "informe de prueba"})
        lineas = [json.loads(ln) for ln in r.text.strip().splitlines() if ln]
        assert any(ln.get("error") == "fallo a media generación" for ln in lineas)
        assert lineas[-1] == {"done": True}


def test_new_job_arranca_en_pendiente_con_expiracion_futura():
    job_id, job = main_module._new_job()
    assert job["status"] == "pending"
    assert job["expires_at"] > time.time()
    assert main_module._jobs[job_id] is job
    main_module._jobs.pop(job_id, None)


def test_cleanup_expired_jobs_borra_solo_los_caducados(monkeypatch):
    """Sin esto los jobs viejos se acumularían en memoria para siempre."""
    main_module._jobs.clear()
    main_module._jobs["viejo"] = {
        "status": "done",
        "result": None,
        "error": None,
        "expires_at": time.time() - 10,
    }
    main_module._jobs["reciente"] = {
        "status": "done",
        "result": None,
        "error": None,
        "expires_at": time.time() + 1000,
    }

    llamadas = {"n": 0}

    async def sleep_falso(segundos):
        llamadas["n"] += 1
        if llamadas["n"] > 1:
            raise asyncio.CancelledError()

    monkeypatch.setattr(main_module.asyncio, "sleep", sleep_falso)

    async def correr():
        with pytest.raises(asyncio.CancelledError):
            await main_module._cleanup_expired_jobs()

    asyncio.run(correr())

    assert "viejo" not in main_module._jobs
    assert "reciente" in main_module._jobs
    main_module._jobs.clear()
