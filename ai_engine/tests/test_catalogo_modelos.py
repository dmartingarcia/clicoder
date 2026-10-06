"""
Tests del catálogo de modelos y de la selección en caliente.
No cargan pesos: comprueban la lógica de listado y de validación.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import main


@pytest.fixture
def catalogo(tmp_path, monkeypatch):
    datos = {
        "repo": "ejemplo/repo",
        "nota_medicion": "misma pasada",
        "modelos": {
            "produccion": {
                "checkpoint": "classifier.pt",
                "thresholds": "thresholds.json",
                "descripcion": "el de siempre",
                "umbral": 0.3,
                "fusion_threshold": 2.9,
                "comparables": {"map_test": 0.4342, "f1_micro_test": 0.4872},
            },
            "otro": {
                "checkpoint": "classifier-otro.pt",
                "thresholds": "thresholds-otro.json",
                "descripcion": "alternativo",
                "umbral": 0.2,
                "fusion_threshold": 2.1,
                "comparables": {"map_test": 0.4535, "f1_micro_test": 0.4972},
            },
        },
    }
    (tmp_path / "models.json").write_text(json.dumps(datos), encoding="utf-8")
    (tmp_path / "classifier.pt").write_bytes(b"x")
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    return tmp_path


def test_sin_catalogo_devuelve_vacio(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    assert main._catalogo_modelos() == {}


def test_catalogo_ilegible_no_rompe(tmp_path, monkeypatch):
    (tmp_path / "models.json").write_text("{esto no es json", encoding="utf-8")
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    assert main._catalogo_modelos() == {}


def test_lee_los_modelos_del_catalogo(catalogo):
    assert sorted(main._catalogo_modelos()["modelos"]) == ["otro", "produccion"]


def test_distingue_lo_descargado_de_lo_que_solo_esta_en_el_catalogo(catalogo):
    """Un modelo del catálogo puede no estar en disco: pesa 2 GB y se baja aparte."""
    modelos = main._catalogo_modelos()["modelos"]
    assert (catalogo / modelos["produccion"]["checkpoint"]).exists()
    assert not (catalogo / modelos["otro"]["checkpoint"]).exists()


def test_cada_modelo_trae_su_propio_umbral_de_fusion(catalogo):
    """Heredar el umbral del modelo anterior degradaría la fusión en silencio."""
    modelos = main._catalogo_modelos()["modelos"]
    assert modelos["produccion"]["fusion_threshold"] != modelos["otro"]["fusion_threshold"]
    for meta in modelos.values():
        assert "umbral" in meta and "fusion_threshold" in meta


def test_las_metricas_comparables_estan_presentes(catalogo):
    for meta in main._catalogo_modelos()["modelos"].values():
        assert {"map_test", "f1_micro_test"} <= set(meta["comparables"])


def test_el_catalogo_real_del_repo_es_valido():
    """El models.json versionado debe poder leerse y tener la forma que espera el motor."""
    ruta = Path(__file__).parent.parent / "model" / "models.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["modelos"], "el catálogo no puede estar vacío"
    for nombre, meta in datos["modelos"].items():
        assert meta["checkpoint"].endswith(".pt"), nombre
        assert meta["thresholds"].endswith(".json"), nombre
        assert "fusion_threshold" in meta, nombre
        assert "map_test" in meta["comparables"], nombre


def test_los_nombres_del_catalogo_son_los_que_deja_la_descarga():
    """`make model-download NAME=x` guarda `x.pt` y `x.thresholds.json`, con el nombre remoto.

    Si el catálogo declara otros, /admin/models busca un fichero que la descarga nunca crea y
    responde 404 «no está descargado» justo después de haberlo descargado. Ya pasó con zlpr-map.
    """
    ruta = Path(__file__).parent.parent / "model" / "models.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    for nombre, meta in datos["modelos"].items():
        if nombre == "produccion":  # el de siempre se llama classifier.pt en el repositorio
            assert meta["checkpoint"] == "classifier.pt"
            assert meta["thresholds"] == "thresholds.json"
        else:
            assert meta["checkpoint"] == f"{nombre}.pt", nombre
            assert meta["thresholds"] == f"{nombre}.thresholds.json", nombre
