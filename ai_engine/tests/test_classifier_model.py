"""Tests de CIE10Classifier: construcción, predict() y el envoltorio de explain()."""

import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).parent.parent))

import classifier as clf_module


class FakeEncoder(torch.nn.Module):
    """Encoder sin parámetros: la salida no depende de la entrada, solo de la forma."""

    def __init__(self, hidden_size=8):
        super().__init__()
        self.config = types.SimpleNamespace(hidden_size=hidden_size)

    def forward(self, input_ids, attention_mask):
        batch, seq_len = input_ids.shape
        return types.SimpleNamespace(
            last_hidden_state=torch.zeros(batch, seq_len, self.config.hidden_size)
        )


class FakeEncoding(dict):
    def __init__(self, data, word_ids_list):
        super().__init__(data)
        self._word_ids = word_ids_list

    def word_ids(self):
        return self._word_ids


class FakeTokenizer:
    """Un token por palabra separada por espacios, más CLS/SEP. Suficiente para
    ejercitar el padding y el agrupado de posiciones por palabra sin spaCy ni HF."""

    mask_token_id = 999
    pad_token_id = 0

    def __call__(
        self, text, max_length=16, padding=None, truncation=True, return_tensors=None, **_kw
    ):
        words = text.split()
        ids = [1, *range(10, 10 + len(words)), 2]
        word_ids = [None, *range(len(words)), None]
        if truncation and len(ids) > max_length:
            ids, word_ids = ids[:max_length], word_ids[:max_length]
        attention = [1] * len(ids)
        if padding == "max_length":
            pad_n = max_length - len(ids)
            ids = ids + [self.pad_token_id] * pad_n
            attention = attention + [0] * pad_n
            word_ids = word_ids + [None] * pad_n
        if return_tensors == "pt":
            data = {"input_ids": torch.tensor([ids]), "attention_mask": torch.tensor([attention])}
        else:
            data = {"input_ids": ids, "attention_mask": attention}
        return FakeEncoding(data, word_ids)


CODE_TO_IDX = {"I10": 0, "E11.9": 1, "E11": 2, "J45": 3}


@pytest.fixture
def clasificador(tmp_path, monkeypatch):
    """Con la capa final a peso cero, la salida es siempre el sesgo: predict() se
    puede probar sin depender de lo que devuelva el encoder falso."""
    monkeypatch.setattr(clf_module.AutoModel, "from_pretrained", lambda name: FakeEncoder())
    monkeypatch.setattr(clf_module.AutoTokenizer, "from_pretrained", lambda name: FakeTokenizer())

    config = {"model_name": "fake/modelo", "max_length": 16, "threshold": 0.5}
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")

    modelo_temporal = clf_module._FlatClassifier("fake/modelo", num_codes=len(CODE_TO_IDX))
    with torch.no_grad():
        modelo_temporal.classifier.weight.zero_()
        modelo_temporal.classifier.bias.copy_(torch.tensor([3.0, 2.0, 2.0, -3.0]))
    ckpt = {
        "code_to_idx": CODE_TO_IDX,
        "idx_to_code": {str(v): k for k, v in CODE_TO_IDX.items()},
        "model_state_dict": modelo_temporal.state_dict(),
    }
    monkeypatch.setattr(clf_module.torch, "load", lambda *a, **kw: ckpt)

    return clf_module.CIE10Classifier(str(tmp_path), device="cpu")


class TestInit:
    def test_carga_el_codigo_a_indice_del_checkpoint(self, clasificador):
        assert clasificador.code_to_idx == CODE_TO_IDX

    def test_sin_capitulos_en_disco_el_diccionario_queda_vacio(self, clasificador):
        assert clasificador.chapters == {}

    def test_los_overrides_pisan_la_config_del_fichero(self, tmp_path, monkeypatch):
        """El cambio de modelo en caliente necesita imponer su propio umbral sin
        tocar config.json, que sigue describiendo el modelo por defecto."""
        monkeypatch.setattr(clf_module.AutoModel, "from_pretrained", lambda name: FakeEncoder())
        monkeypatch.setattr(
            clf_module.AutoTokenizer, "from_pretrained", lambda name: FakeTokenizer()
        )
        (tmp_path / "config.json").write_text(
            json.dumps({"model_name": "fake/modelo", "max_length": 16, "threshold": 0.5}),
            encoding="utf-8",
        )
        modelo_temporal = clf_module._FlatClassifier("fake/modelo", num_codes=1)
        ckpt = {
            "code_to_idx": {"I10": 0},
            "idx_to_code": {"0": "I10"},
            "model_state_dict": modelo_temporal.state_dict(),
        }
        monkeypatch.setattr(clf_module.torch, "load", lambda *a, **kw: ckpt)

        clf = clf_module.CIE10Classifier(str(tmp_path), device="cpu", overrides={"threshold": 0.9})
        assert clf.config["threshold"] == 0.9

    def test_carga_los_capitulos_si_el_fichero_existe(self, tmp_path, monkeypatch):
        monkeypatch.setattr(clf_module.AutoModel, "from_pretrained", lambda name: FakeEncoder())
        monkeypatch.setattr(
            clf_module.AutoTokenizer, "from_pretrained", lambda name: FakeTokenizer()
        )
        (tmp_path / "config.json").write_text(
            json.dumps({"model_name": "fake/modelo", "max_length": 16}), encoding="utf-8"
        )
        (tmp_path / "cie10_chapters.json").write_text(
            json.dumps({"IX": {"name": "Circulatorio"}}), encoding="utf-8"
        )
        modelo_temporal = clf_module._FlatClassifier("fake/modelo", num_codes=1)
        ckpt = {
            "code_to_idx": {"I10": 0},
            "idx_to_code": {"0": "I10"},
            "model_state_dict": modelo_temporal.state_dict(),
        }
        monkeypatch.setattr(clf_module.torch, "load", lambda *a, **kw: ckpt)

        clf = clf_module.CIE10Classifier(str(tmp_path), device="cpu")
        assert clf.chapters["IX"]["name"] == "Circulatorio"

    def test_umbrales_por_clase_se_cargan_si_el_fichero_existe(self, tmp_path, monkeypatch):
        monkeypatch.setattr(clf_module.AutoModel, "from_pretrained", lambda name: FakeEncoder())
        monkeypatch.setattr(
            clf_module.AutoTokenizer, "from_pretrained", lambda name: FakeTokenizer()
        )
        config = {
            "model_name": "fake/modelo",
            "max_length": 16,
            "thresholds_file": "thresholds.json",
            "use_per_class_thresholds": True,
        }
        (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
        (tmp_path / "thresholds.json").write_text(
            json.dumps({"per_class_thresholds": [0.3]}), encoding="utf-8"
        )
        modelo_temporal = clf_module._FlatClassifier("fake/modelo", num_codes=1)
        ckpt = {
            "code_to_idx": {"I10": 0},
            "idx_to_code": {"0": "I10"},
            "model_state_dict": modelo_temporal.state_dict(),
        }
        monkeypatch.setattr(clf_module.torch, "load", lambda *a, **kw: ckpt)

        clf = clf_module.CIE10Classifier(str(tmp_path), device="cpu")
        assert clf.per_class_thresholds == [0.3]

        config.pop("use_per_class_thresholds")
        (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
        clf = clf_module.CIE10Classifier(str(tmp_path), device="cpu")
        assert clf.per_class_thresholds is None


class TestPredict:
    def test_filtra_por_debajo_del_umbral(self, clasificador):
        codigos = [p["code"] for p in clasificador.predict("cualquier texto")]
        assert "J45" not in codigos

    def test_el_hijo_desplaza_al_padre(self, clasificador):
        """E11.9 y E11 pasan el umbral a la vez: reportar el padre sería redundante
        con el hijo, que ya es más específico."""
        codigos = [p["code"] for p in clasificador.predict("cualquier texto")]
        assert "E11.9" in codigos
        assert "E11" not in codigos

    def test_ordena_por_probabilidad_descendente(self, clasificador):
        probs = [p["probability"] for p in clasificador.predict("cualquier texto")]
        assert probs == sorted(probs, reverse=True)

    def test_top_k_limita_los_resultados(self, clasificador):
        assert len(clasificador.predict("cualquier texto", top_k=1)) == 1

    def test_incluye_el_capitulo_y_su_nombre(self, clasificador):
        i10 = next(p for p in clasificador.predict("cualquier texto") if p["code"] == "I10")
        assert i10["chapter"] == "IX"

    def test_incluye_la_descripcion_si_se_pide(self, clasificador):
        resultado = clasificador.predict(
            "texto", code_descriptions={"I10": "Hipertensión esencial"}
        )
        i10 = next(p for p in resultado if p["code"] == "I10")
        assert i10["description"] == "Hipertensión esencial"

    def test_sin_descripciones_no_agrega_el_campo(self, clasificador):
        i10 = next(p for p in clasificador.predict("texto") if p["code"] == "I10")
        assert "description" not in i10

    def test_un_umbral_explicito_sustituye_al_de_config(self, clasificador):
        # Con umbral 0.9 solo I10 (0.95) sigue por encima.
        codigos = [p["code"] for p in clasificador.predict("texto", threshold=0.9)]
        assert codigos == ["I10"]

    def test_logit_bonus_sin_score_threshold_es_un_error_de_uso(self, clasificador):
        bonus = np.zeros(len(CODE_TO_IDX), dtype=np.float32)
        with pytest.raises(ValueError):
            clasificador.predict("texto", logit_bonus=bonus)

    def test_la_fusion_puede_rescatar_un_codigo_bajo_el_umbral_normal(self, clasificador):
        """J45 no llega al umbral por sí solo: con bonificación del diccionario, sí."""
        bonus = np.zeros(len(CODE_TO_IDX), dtype=np.float32)
        bonus[CODE_TO_IDX["J45"]] = 10.0
        resultado = clasificador.predict("texto", logit_bonus=bonus, score_threshold=0.0)
        j45 = next(p for p in resultado if p["code"] == "J45")
        assert j45["dict_bonus"] == pytest.approx(10.0)
        assert j45["probability"] < 0.5  # sigue siendo la probabilidad del modelo, no la fusionada

    def test_en_fusion_descarta_lo_que_no_llega_al_umbral_de_puntuacion(self, clasificador):
        bonus = np.zeros(len(CODE_TO_IDX), dtype=np.float32)
        resultado = clasificador.predict("texto", logit_bonus=bonus, score_threshold=2.5)
        # Con las puntuaciones fijas [3.0, 2.0, 2.0, -3.0], solo I10 llega a 2.5.
        assert [p["code"] for p in resultado] == ["I10"]

    def test_en_fusion_ordena_por_puntuacion_no_por_probabilidad(self, clasificador):
        bonus = np.zeros(len(CODE_TO_IDX), dtype=np.float32)
        bonus[CODE_TO_IDX["J45"]] = 100.0  # dispara su puntuación muy por encima del resto
        resultado = clasificador.predict("texto", logit_bonus=bonus, score_threshold=0.0)
        assert resultado[0]["code"] == "J45"


class TestExplainEnvoltorio:
    def test_lista_de_codigos_vacia_no_llama_a_nada(self, clasificador):
        assert clasificador.explain("texto cualquiera", []) == {}

    def test_sin_mask_token_no_se_puede_explicar(self, clasificador, monkeypatch):
        monkeypatch.setattr(clasificador.tokenizer, "mask_token_id", None)
        assert clasificador.explain("texto largo de prueba", [0]) == {0: []}

    def test_palabras_demasiado_cortas_no_dejan_candidatas(self, clasificador):
        # Ninguna palabra llega a los 4 caracteres exigidos.
        assert clasificador.explain("yo lo vi ya", [0]) == {0: []}

    def test_delega_en_el_metodo_pedido(self, clasificador, monkeypatch):
        llamadas = []

        def metodo_falso(ctx, candidatas):
            llamadas.append(list(candidatas))
            return {w: torch.tensor([1.0]) for w in candidatas}

        monkeypatch.setitem(clf_module.METODOS_EXPLAIN, "exhaustivo", metodo_falso)
        clasificador.explain("hipertension arterial elevada", [0], method="exhaustivo")
        assert llamadas

    def test_metodo_desconocido_cae_al_de_por_defecto(self, clasificador, monkeypatch):
        usados = []
        original = clf_module.METODOS_EXPLAIN[clf_module.EXPLAIN_POR_DEFECTO]

        def espia(ctx, candidatas):
            usados.append(True)
            return original(ctx, candidatas)

        monkeypatch.setitem(clf_module.METODOS_EXPLAIN, clf_module.EXPLAIN_POR_DEFECTO, espia)
        clasificador.explain("hipertension arterial elevada", [0], method="no_existe")
        assert usados

    def test_with_scores_normaliza_a_que_sumen_uno(self, clasificador, monkeypatch):
        def metodo_falso(ctx, candidatas):
            pesos = [3.0, 1.0] + [0.0] * (len(candidatas) - 2)
            return {w: torch.tensor([pesos[i]]) for i, w in enumerate(candidatas)}

        monkeypatch.setitem(clf_module.METODOS_EXPLAIN, "exhaustivo", metodo_falso)
        resultado = clasificador.explain(
            "hipertension arterial elevada cronica", [0], method="exhaustivo", with_scores=True
        )
        total = sum(peso for _, peso in resultado[0])
        assert total == pytest.approx(1.0)

    def test_top_k_limita_los_terminos_devueltos(self, clasificador, monkeypatch):
        def metodo_falso(ctx, candidatas):
            return {w: torch.tensor([float(i + 1)]) for i, w in enumerate(candidatas)}

        monkeypatch.setitem(clf_module.METODOS_EXPLAIN, "exhaustivo", metodo_falso)
        resultado = clasificador.explain(
            "hipertension arterial elevada cronica severa",
            [0],
            method="exhaustivo",
            top_k=2,
        )
        assert len(resultado[0]) == 2

    def test_un_fallo_del_metodo_no_rompe_la_peticion(self, clasificador, monkeypatch):
        """explain() alimenta directamente una respuesta HTTP: un error aquí no puede
        tirar la petición entera cuando el usuario solo pidió ver los códigos."""

        def metodo_roto(ctx, candidatas):
            raise RuntimeError("fallo simulado")

        monkeypatch.setitem(clf_module.METODOS_EXPLAIN, "exhaustivo", metodo_roto)
        resultado = clasificador.explain("hipertension arterial elevada", [0], method="exhaustivo")
        assert resultado == {0: []}


def test_load_code_descriptions_avisa_si_el_fichero_esta_vacio(tmp_path):
    (tmp_path / "code_descriptions.json").write_text("", encoding="utf-8")
    assert clf_module.load_code_descriptions(str(tmp_path)) == {}
