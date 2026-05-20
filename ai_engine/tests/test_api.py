"""
Tests for the FastAPI endpoints in main.py.
Uses TestClient with a mocked classifier and dict_classifier so no
model weights are required.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import main as main_module


# =============================================================================
# Helpers
# =============================================================================

def _no_model_client():
    """
    Return a TestClient configured so the lifespan does NOT load any model.
    We point MODEL_DIR at a non-existent path so the lifespan warning branch
    fires and leaves classifier / dict_classifier as None.
    """
    old = os.environ.get("MODEL_DIR")
    os.environ["MODEL_DIR"] = "/nonexistent_test_model_dir"
    main_module.classifier = None
    main_module.dict_classifier = None
    main_module.code_descriptions = {}
    client = TestClient(main_module.app)
    if old is None:
        del os.environ["MODEL_DIR"]
    else:
        os.environ["MODEL_DIR"] = old
    return client


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_bert_predictions():
    return [
        {"code": "I10", "probability": 0.92, "chapter": "IX", "chapter_name": "Enfermedades del sistema circulatorio", "description": "Hipertensión esencial"},
        {"code": "E11", "probability": 0.81, "chapter": "IV", "chapter_name": "Enfermedades endocrinas", "description": "Diabetes tipo 2"},
    ]


@pytest.fixture
def mock_dict_predictions():
    return [
        {"code": "I10", "confidence": 1.0, "matched_terms": ["hipertension"]},
    ]


@pytest.fixture
def client_with_bert(mock_bert_predictions):
    """TestClient with a BERT classifier mock injected AFTER lifespan."""
    mock_clf = MagicMock()
    mock_clf.predict.return_value = mock_bert_predictions

    # Use no-model client so lifespan does not load the real model
    old = os.environ.get("MODEL_DIR")
    os.environ["MODEL_DIR"] = "/nonexistent_test_model_dir"

    with TestClient(main_module.app) as client:
        # Inject mock AFTER lifespan has run (lifespan left classifier=None)
        main_module.classifier = mock_clf
        main_module.dict_classifier = None
        main_module.code_descriptions = {"I10": "Hipertensión esencial", "E11": "Diabetes tipo 2"}
        yield client

    main_module.classifier = None
    main_module.dict_classifier = None
    main_module.code_descriptions = {}
    if old is None:
        os.environ.pop("MODEL_DIR", None)
    else:
        os.environ["MODEL_DIR"] = old


@pytest.fixture
def client_with_dict(mock_dict_predictions):
    """TestClient with a dict classifier mock."""
    mock_clf = MagicMock()
    mock_clf.predict.return_value = mock_dict_predictions

    old = os.environ.get("MODEL_DIR")
    os.environ["MODEL_DIR"] = "/nonexistent_test_model_dir"

    with TestClient(main_module.app) as client:
        main_module.classifier = None
        main_module.dict_classifier = mock_clf
        main_module.code_descriptions = {"I10": "Hipertensión esencial"}
        yield client

    main_module.classifier = None
    main_module.dict_classifier = None
    main_module.code_descriptions = {}
    if old is None:
        os.environ.pop("MODEL_DIR", None)
    else:
        os.environ["MODEL_DIR"] = old


@pytest.fixture
def client_no_model():
    """TestClient with no classifier loaded."""
    old = os.environ.get("MODEL_DIR")
    os.environ["MODEL_DIR"] = "/nonexistent_test_model_dir"

    with TestClient(main_module.app) as client:
        yield client

    main_module.classifier = None
    main_module.dict_classifier = None
    main_module.code_descriptions = {}
    if old is None:
        os.environ.pop("MODEL_DIR", None)
    else:
        os.environ["MODEL_DIR"] = old


# =============================================================================
# GET /  — health check
# =============================================================================

class TestHealthCheck:
    def test_returns_online_status(self, client_no_model):
        resp = client_no_model.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "online"

    def test_model_loaded_false_when_no_model(self, client_no_model):
        resp = client_no_model.get("/")
        assert resp.json()["model_loaded"] is False

    def test_model_loaded_true_when_bert_present(self, client_with_bert):
        resp = client_with_bert.get("/")
        assert resp.json()["model_loaded"] is True

    def test_dict_loaded_true_when_dict_present(self, client_with_dict):
        resp = client_with_dict.get("/")
        assert resp.json()["dict_loaded"] is True

    def test_response_contains_required_keys(self, client_no_model):
        data = client_no_model.get("/").json()
        assert "status" in data
        assert "model_loaded" in data
        assert "dict_loaded" in data


# =============================================================================
# POST /predict  — BERT engine
# =============================================================================

class TestPredictBert:
    def test_returns_cards_list(self, client_with_bert):
        resp = client_with_bert.post("/predict", json={"text": "Paciente con hipertensión arterial"})
        assert resp.status_code == 200
        assert isinstance(resp.json()["cards"], list)

    def test_returns_summary_codes_recommendations_cards(self, client_with_bert):
        resp = client_with_bert.post("/predict", json={"text": "Paciente con hipertensión arterial"})
        card_types = [c["type"] for c in resp.json()["cards"]]
        assert "summary" in card_types
        assert "codes" in card_types
        assert "recommendations" in card_types

    def test_codes_card_contains_required_fields(self, client_with_bert):
        resp = client_with_bert.post("/predict", json={"text": "Paciente con hipertensión arterial"})
        codes_card = next(c for c in resp.json()["cards"] if c["type"] == "codes")
        for entry in codes_card["content"]:
            assert "code" in entry
            assert "confidence" in entry
            assert entry["engine"] == "bert"

    def test_summary_mentions_word_count(self, client_with_bert):
        text = "Paciente con hipertensión arterial y diabetes"
        resp = client_with_bert.post("/predict", json={"text": text})
        summary = next(c for c in resp.json()["cards"] if c["type"] == "summary")
        assert str(len(text.split())) in summary["content"]

    def test_empty_text_returns_422(self, client_with_bert):
        resp = client_with_bert.post("/predict", json={"text": "   "})
        assert resp.status_code == 422

    def test_missing_model_returns_503(self, client_no_model):
        resp = client_no_model.post("/predict", json={"text": "Paciente con hipertensión"})
        assert resp.status_code == 503

    def test_calls_classifier_predict_with_text(self, client_with_bert):
        text = "Informe clínico de prueba para verificar llamada"
        client_with_bert.post("/predict", json={"text": text})
        main_module.classifier.predict.assert_called_once()
        assert main_module.classifier.predict.call_args[0][0] == text

    def test_top_k_is_10(self, client_with_bert):
        client_with_bert.post("/predict", json={"text": "Texto de prueba clínico"})
        assert main_module.classifier.predict.call_args[0][1] == 10


# =============================================================================
# POST /predict  — dict engine
# =============================================================================

class TestPredictDict:
    def test_returns_cards_list(self, client_with_dict):
        resp = client_with_dict.post("/predict", json={"text": "Paciente con hipertensión", "engine": "dict"})
        assert resp.status_code == 200
        assert "cards" in resp.json()

    def test_codes_card_engine_is_dict(self, client_with_dict):
        resp = client_with_dict.post("/predict", json={"text": "Paciente con hipertensión", "engine": "dict"})
        codes_card = next(c for c in resp.json()["cards"] if c["type"] == "codes")
        for entry in codes_card["content"]:
            assert entry["engine"] == "dict"

    def test_codes_card_includes_matched_terms(self, client_with_dict):
        resp = client_with_dict.post("/predict", json={"text": "Paciente con hipertensión", "engine": "dict"})
        codes_card = next(c for c in resp.json()["cards"] if c["type"] == "codes")
        for entry in codes_card["content"]:
            assert "matched_terms" in entry

    def test_missing_dict_model_returns_503(self, client_no_model):
        resp = client_no_model.post("/predict", json={"text": "Paciente", "engine": "dict"})
        assert resp.status_code == 503

    def test_empty_text_returns_422(self, client_with_dict):
        resp = client_with_dict.post("/predict", json={"text": "", "engine": "dict"})
        assert resp.status_code == 422

    def test_reason_mentions_matched_terms(self, client_with_dict):
        resp = client_with_dict.post("/predict", json={"text": "Paciente con hipertensión", "engine": "dict"})
        codes_card = next(c for c in resp.json()["cards"] if c["type"] == "codes")
        for entry in codes_card["content"]:
            assert "Términos encontrados" in entry["reason"]
