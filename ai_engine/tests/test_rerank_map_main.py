"""Test de main() de rerank_map.py de punta a punta."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import baseline_dict as baseline_dict_module
import ensemble_eval
import rerank_map

CODE_TO_IDX = {"A01": 0, "B02": 1, "C03": 2}


def _fake_infer(ckpt_path, texts, model_name, max_length, batch_size, device):
    rng = np.random.default_rng(len(texts))
    probs = rng.uniform(0.01, 0.99, size=(len(texts), len(CODE_TO_IDX))).astype(np.float32)
    return probs, dict(CODE_TO_IDX)


def _escribir_split(path, filas):
    with open(path, "w", encoding="utf-8") as f:
        f.write("text,labels\n")
        for texto, labels in filas:
            f.write(f"{texto},{labels}\n")


@pytest.fixture
def datos(tmp_path):
    train = tmp_path / "train.csv"
    val = tmp_path / "val.csv"
    test = tmp_path / "test.csv"
    _escribir_split(train, [("nota train uno", "A01"), ("nota train dos", "B02")])
    _escribir_split(
        val,
        [("nota val uno", "A01;B02"), ("nota val dos", "C03"), ("nota val tres", "A01")],
    )
    _escribir_split(
        test,
        [("nota test uno", "B02"), ("nota test dos", "A01;C03"), ("nota test tres", "C03")],
    )
    return train, val, test


def _argv_base(datos, tmp_path, extra=()):
    train, val, test = datos
    return [
        "rerank_map.py",
        "--ckpt",
        "fake.pt",
        "--label",
        "prueba",
        "--train_file",
        str(train),
        "--val_file",
        str(val),
        "--test_file",
        str(test),
        "--cache_dir",
        str(tmp_path / "cache"),
        "--out",
        str(tmp_path / "out.json"),
        "--device",
        "cpu",
        *extra,
    ]


def test_main_sin_diccionario_escribe_los_resultados(datos, tmp_path, monkeypatch):
    monkeypatch.setattr(ensemble_eval, "infer", _fake_infer)
    monkeypatch.setattr(sys, "argv", _argv_base(datos, tmp_path))

    rerank_map.main()

    resultados = json.loads((tmp_path / "out.json").read_text())
    assert "rerank_test" in resultados
    assert "solo_calibracion" in resultados["ablacion"]
    assert 0.0 <= resultados["f1"]["f1_micro_test"] <= 1.0


def test_main_con_diccionario_fusiona_el_bonus_y_lo_reporta(datos, tmp_path, monkeypatch):
    class DictClassifierFalso:
        def __init__(self, path):
            pass

        def predict(self, text):
            return [{"code": "A01", "confidence": 0.9}] if "uno" in text else []

    monkeypatch.setattr(ensemble_eval, "infer", _fake_infer)
    monkeypatch.setattr(baseline_dict_module, "DictClassifier", DictClassifierFalso)
    monkeypatch.setattr(
        sys, "argv", _argv_base(datos, tmp_path, extra=["--dict_patterns", "patrones.json"])
    )

    rerank_map.main()

    resultados = json.loads((tmp_path / "out.json").read_text())
    assert "solo_diccionario" in resultados["ablacion"]


def test_main_un_diccionario_roto_desactiva_la_fusion_sin_tirar_el_run(
    datos, tmp_path, monkeypatch
):
    """Si el diccionario falla (spaCy no disponible), no debe perderse el run tras pagar la inferencia."""

    class DictClassifierRoto:
        def __init__(self, path):
            raise RuntimeError("spaCy no disponible")

    monkeypatch.setattr(ensemble_eval, "infer", _fake_infer)
    monkeypatch.setattr(baseline_dict_module, "DictClassifier", DictClassifierRoto)
    monkeypatch.setattr(
        sys, "argv", _argv_base(datos, tmp_path, extra=["--dict_patterns", "patrones.json"])
    )

    rerank_map.main()

    resultados = json.loads((tmp_path / "out.json").read_text())
    assert "solo_diccionario" not in resultados["ablacion"]
