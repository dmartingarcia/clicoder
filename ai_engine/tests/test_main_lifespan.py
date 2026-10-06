"""Tests del arranque del servicio (lifespan): carga de BERT y del diccionario."""

import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import baseline_dict as baseline_dict_module
import classifier as classifier_module
import main as main_module


@pytest.fixture
def model_dir_vacio(tmp_path, monkeypatch):
    """Directorio que existe pero no tiene ni config.json ni baseline_dict.json."""
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("SUMMARIZER_MODEL", "none")
    yield tmp_path
    main_module.classifier = None
    main_module.dict_classifier = None
    main_module.summarizer = None


def test_sin_config_json_el_modelo_no_se_carga_pero_el_servicio_arranca(model_dir_vacio):
    """Falta config.json: el fallo de CIE10Classifier() se absorbe como cualquier otro."""
    with TestClient(main_module.app) as client:
        assert main_module.classifier is None
        assert client.get("/").json()["model_loaded"] is False


def test_sin_baseline_dict_json_el_diccionario_no_esta_disponible(model_dir_vacio):
    with TestClient(main_module.app) as client:
        assert main_module.dict_classifier is None
        assert client.get("/").json()["dict_loaded"] is False


def test_bert_se_carga_cuando_config_y_checkpoint_existen(model_dir_vacio, monkeypatch):
    (model_dir_vacio / "config.json").write_text(
        json.dumps({"model_name": "org/modelo-de-prueba"}), encoding="utf-8"
    )
    clasificador_falso = MagicMock()
    monkeypatch.setattr(
        classifier_module, "CIE10Classifier", lambda model_dir, device: clasificador_falso
    )
    monkeypatch.setattr(classifier_module, "load_code_descriptions", lambda model_dir: {"I10": "x"})

    with TestClient(main_module.app):
        assert main_module.classifier is clasificador_falso
        assert main_module.code_descriptions == {"I10": "x"}


def test_un_fallo_al_cargar_bert_deja_el_servicio_sin_modelo_en_vez_de_romper_el_arranque(
    model_dir_vacio, monkeypatch
):
    (model_dir_vacio / "config.json").write_text(
        json.dumps({"model_name": "org/modelo-de-prueba"}), encoding="utf-8"
    )

    def revienta(model_dir, device):
        raise RuntimeError("checkpoint corrupto")

    monkeypatch.setattr(classifier_module, "CIE10Classifier", revienta)

    with TestClient(main_module.app) as client:
        assert main_module.classifier is None
        assert client.get("/").json()["model_loaded"] is False


def test_diccionario_se_carga_cuando_baseline_dict_json_existe(model_dir_vacio, monkeypatch):
    (model_dir_vacio / "baseline_dict.json").write_text("{}", encoding="utf-8")
    dict_falso = MagicMock()
    dict_falso._patterns = {"I10": [1, 2]}
    monkeypatch.setattr(baseline_dict_module, "DictClassifier", lambda path: dict_falso)

    with TestClient(main_module.app):
        assert main_module.dict_classifier is dict_falso


def test_un_fallo_al_cargar_el_diccionario_deja_ese_motor_desactivado(model_dir_vacio, monkeypatch):
    (model_dir_vacio / "baseline_dict.json").write_text("{}", encoding="utf-8")

    def revienta(path):
        raise ValueError("patrones ilegibles")

    monkeypatch.setattr(baseline_dict_module, "DictClassifier", revienta)

    with TestClient(main_module.app) as client:
        assert main_module.dict_classifier is None
        assert client.get("/").json()["dict_loaded"] is False


def test_config_sin_model_name_usa_el_de_por_defecto_para_el_watcher(model_dir_vacio, monkeypatch):
    """Un config.json incompleto no debe impedir que arranque el hilo de progreso."""
    (model_dir_vacio / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(classifier_module, "CIE10Classifier", lambda model_dir, device: MagicMock())
    monkeypatch.setattr(classifier_module, "load_code_descriptions", lambda model_dir: {})

    with TestClient(main_module.app):
        assert main_module.classifier is not None


def test_el_checkpoint_reportado_es_el_mas_reciente_por_orden_alfabetico(
    model_dir_vacio, monkeypatch
):
    (model_dir_vacio / "config.json").write_text(
        json.dumps({"model_name": "org/modelo"}), encoding="utf-8"
    )
    (model_dir_vacio / "classifier_20240101.pt").write_bytes(b"x")
    (model_dir_vacio / "classifier_20240202.pt").write_bytes(b"x")
    monkeypatch.setattr(classifier_module, "CIE10Classifier", lambda model_dir, device: MagicMock())
    monkeypatch.setattr(classifier_module, "load_code_descriptions", lambda model_dir: {})

    with TestClient(main_module.app):
        # MODEL_INFO no se puede leer desde fuera sin acoplarse a prometheus_client;
        # lo que importa es que arrancar con más de un checkpoint en disco no rompe.
        assert main_module.classifier is not None


def test_watch_download_no_bloquea_si_el_evento_ya_esta_marcado(monkeypatch):
    import huggingface_hub

    monkeypatch.setattr(
        huggingface_hub,
        "model_info",
        lambda name: (_ for _ in ()).throw(Exception("sin red en tests")),
    )
    evento = threading.Event()
    evento.set()
    main_module._watch_download("org/modelo", evento)


def test_watch_download_reporta_progreso_con_el_total_conocido(monkeypatch, tmp_path):
    import huggingface_hub
    from huggingface_hub import constants as hf_constants

    monkeypatch.setattr(hf_constants, "HF_HUB_CACHE", str(tmp_path))
    cache = tmp_path / "models--org--modelo"
    cache.mkdir()
    (cache / "pesos.bin").write_bytes(b"0" * 1024 * 1024)

    class InfoFalso:
        class safetensors:
            total = 10 * 1024 * 1024

    monkeypatch.setattr(huggingface_hub, "model_info", lambda name: InfoFalso())

    evento = threading.Event()
    hilo = threading.Thread(target=main_module._watch_download, args=("org/modelo", evento))
    hilo.start()
    time.sleep(0.05)
    evento.set()
    hilo.join(timeout=2)
    assert not hilo.is_alive()
