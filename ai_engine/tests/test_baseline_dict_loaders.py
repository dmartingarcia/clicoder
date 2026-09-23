"""Tests de la carga de diccionarios (diagnoses/procedures/chemicals), la caché en"""

import sys
import types
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import baseline_dict as bd


class TestCache:
    def test_cache_path_crea_el_directorio_si_no_existe(self, tmp_path):
        destino = tmp_path / "sub" / "cache"
        ruta = bd._cache_path(str(destino), "diagnoses", "abc123")
        assert destino.exists()
        assert ruta == str(destino / "diagnoses_abc123.pkl")

    def test_load_cache_sin_fichero_devuelve_none(self, tmp_path):
        assert bd._load_cache(str(tmp_path / "no_existe.pkl")) is None

    def test_save_y_load_cache_recupera_los_mismos_datos(self, tmp_path):
        ruta = str(tmp_path / "datos.pkl")
        bd._save_cache(ruta, {"A01": [("fiebre", 1.0)]})
        assert bd._load_cache(ruta) == {"A01": [("fiebre", 1.0)]}


class TestLemmatize:
    def test_ignora_la_puntuacion(self):
        resultado = bd.lemmatize("hola, tos seca.")
        assert "," not in resultado and "." not in resultado

    def test_normaliza_el_genero_de_los_adjetivos(self):
        assert bd.lemmatize("insuficiencia cardiaca aguda") == "insuficiencia cardiaco agudo"


class _LexFalso:
    def __init__(self, has_vector=True):
        self.has_vector = has_vector
        self.vector = np.zeros(4, dtype=np.float32)


class _VectoresFalsos:
    def __init__(self, candidatos):
        self._candidatos = candidatos  # [(indice, score), ...]

    def most_similar(self, queries, n):
        elegidos = self._candidatos[:n]
        keys = np.array([[i for i, _ in elegidos]])
        scores = np.array([[s for _, s in elegidos]])
        return keys, None, scores


class _VectoresQueFallan:
    def most_similar(self, *a, **kw):
        raise RuntimeError("índice de vectores corrupto")


class _VocabFalso:
    def __init__(self, lex_by_word, vectors, palabras):
        self._lex = lex_by_word
        self.vectors = vectors
        self.strings = palabras  # lista: índice -> palabra

    def __getitem__(self, word):
        return self._lex.get(word, _LexFalso())


@pytest.fixture
def nlp_vec_falso(monkeypatch):
    def _instalar(vocab):
        monkeypatch.setattr(bd, "_get_nlp_vectors", lambda: types.SimpleNamespace(vocab=vocab))

    return _instalar


class TestFindSimilarWords:
    def test_descarta_candidatos_por_debajo_del_umbral(self, nlp_vec_falso):
        palabras = ["hipertenso", "hola"]
        vocab = _VocabFalso(
            {"hipertension": _LexFalso()},
            _VectoresFalsos([(0, 0.9), (1, 0.5)]),
            palabras,
        )
        nlp_vec_falso(vocab)
        assert bd.find_similar_words("hipertension", min_sim=0.8) == ["hipertenso"]

    def test_descarta_candidatos_demasiado_cortos(self, nlp_vec_falso):
        palabras = ["hip"]
        vocab = _VocabFalso({"hipertension": _LexFalso()}, _VectoresFalsos([(0, 0.99)]), palabras)
        nlp_vec_falso(vocab)
        assert bd.find_similar_words("hipertension", min_sim=0.8) == []

    def test_descarta_candidatos_que_son_subcadena_del_original(self, nlp_vec_falso):
        # "hiper" es una variante morfológica de la misma raíz, no un sinónimo real.
        palabras = ["hiper"]
        vocab = _VocabFalso({"hipertension": _LexFalso()}, _VectoresFalsos([(0, 0.99)]), palabras)
        nlp_vec_falso(vocab)
        assert bd.find_similar_words("hipertension", min_sim=0.8) == []

    def test_respeta_el_limite_max_n(self, nlp_vec_falso):
        palabras = ["candidatoa", "candidatob", "candidatoc"]
        vocab = _VocabFalso(
            {"palabra": _LexFalso()},
            _VectoresFalsos([(0, 0.99), (1, 0.98), (2, 0.97)]),
            palabras,
        )
        nlp_vec_falso(vocab)
        assert len(bd.find_similar_words("palabra", min_sim=0.8, max_n=2)) == 2

    def test_sin_vector_propio_no_hay_nada_que_buscar(self, nlp_vec_falso):
        vocab = _VocabFalso({"palabra_rara": _LexFalso(has_vector=False)}, _VectoresFalsos([]), [])
        nlp_vec_falso(vocab)
        assert bd.find_similar_words("palabra_rara") == []

    def test_un_fallo_del_indice_de_vectores_no_rompe_nada(self, nlp_vec_falso):
        vocab = _VocabFalso({"palabra": _LexFalso()}, _VectoresQueFallan(), [])
        nlp_vec_falso(vocab)
        assert bd.find_similar_words("palabra") == []


class _TokenFalso:
    def __init__(self, texto, pos, lemma=None, is_stop=False):
        self.text = texto
        self.pos_ = pos
        self.lemma_ = lemma or texto
        self.is_stop = is_stop


class TestBuildSynonymMap:
    def test_solo_considera_palabras_de_contenido(self, monkeypatch):
        doc = [
            _TokenFalso("hipertension", "NOUN"),
            _TokenFalso("la", "DET"),  # se descarta: no es NOUN/ADJ/VERB/PROPN
            _TokenFalso("de", "ADP", is_stop=True),
        ]
        monkeypatch.setattr(bd, "_get_nlp", lambda: lambda texto: doc)
        monkeypatch.setattr(bd, "find_similar_words", lambda token, **kw: [f"{token}_syn"])

        mapa = bd.build_synonym_map({"hipertension de la aorta"})
        assert mapa == {"hipertension": ["hipertension_syn"]}

    def test_palabras_cortas_se_descartan(self, monkeypatch):
        doc = [_TokenFalso("de", "NOUN")]  # 2 caracteres: por debajo del mínimo de 4
        monkeypatch.setattr(bd, "_get_nlp", lambda: lambda texto: doc)
        monkeypatch.setattr(bd, "find_similar_words", lambda token, **kw: ["algo"])
        assert bd.build_synonym_map({"de"}) == {}

    def test_usa_la_cache_si_existe(self, tmp_path, monkeypatch):
        cache_file = str(tmp_path / "syn.pkl")
        bd._save_cache(cache_file, {"ya": ["cacheado"]})
        llamado = {"n": 0}
        monkeypatch.setattr(bd, "_get_nlp", lambda: llamado.update(n=llamado["n"] + 1))
        assert bd.build_synonym_map({"cualquier cosa"}, cache_file=cache_file) == {
            "ya": ["cacheado"]
        }
        assert llamado["n"] == 0  # no se llegó a tocar spaCy

    def test_guarda_en_cache_tras_calcular(self, tmp_path, monkeypatch):
        cache_file = str(tmp_path / "syn.pkl")
        doc = [_TokenFalso("hipertension", "NOUN")]
        monkeypatch.setattr(bd, "_get_nlp", lambda: lambda texto: doc)
        monkeypatch.setattr(bd, "find_similar_words", lambda token, **kw: ["sinonimo"])

        bd.build_synonym_map({"hipertension"}, cache_file=cache_file)
        assert bd._load_cache(cache_file) == {"hipertension": ["sinonimo"]}


def test_expand_term_genera_una_variante_por_sinonimo():
    variantes = bd.expand_term("dolor agudo", {"agudo": ["intenso", "severo"]})
    assert "dolor intenso" in variantes
    assert "dolor severo" in variantes
    assert variantes[0] == bd.lemmatize("dolor agudo")


def test_expand_term_no_repite_variantes_iguales():
    variantes = bd.expand_term("dolor agudo", {"agudo": ["agudo"]})
    assert variantes.count(bd.lemmatize("dolor agudo")) == 1


def test_expand_description_ignora_partes_vacias():
    assert bd.expand_description("cólera||tifoidea") == ["cólera", "tifoidea"]


def test_extract_ngrams_descarta_ventanas_con_digitos():
    ngramas = bd.extract_ngrams("dosis 5 mg diaria", min_n=2, max_n=2)
    assert not any(any(c.isdigit() for c in ng) for ng in ngramas)
    assert "mg diaria" in ngramas


@pytest.fixture
def lemmatize_identidad(monkeypatch):
    """Sustituye lemmatize por minúsculas planas: lematizar bien ya lo prueba TestLemmatize."""
    monkeypatch.setattr(bd, "lemmatize", lambda t: t.lower())


class TestBuildBlockPatterns:
    pytestmark = pytest.mark.usefixtures("lemmatize_identidad")

    def test_lematiza_y_compila_un_patron_por_descripcion(self):
        pares = [("A01", "Fiebre Tifoidea")]
        resultado = bd._build_block_patterns(pares, "diagnoses", 3, None, [], confidence=1.0)
        assert resultado["A01"][0][1] == 1.0
        assert resultado["A01"][0][0].search("con fiebre tifoidea confirmada")

    def test_descarta_descripciones_mas_cortas_que_min_len(self):
        resultado = bd._build_block_patterns([("A01", "ab")], "diagnoses", 5, None, [], 1.0)
        assert "A01" not in resultado

    def test_usa_la_cache_en_la_segunda_llamada(self, tmp_path, monkeypatch):
        pares = [("A01", "Fiebre tifoidea")]
        claves = ["v1"]
        bd._build_block_patterns(pares, "diagnoses", 3, str(tmp_path), claves, 1.0)

        llamadas = {"n": 0}
        original = bd.lemmatize

        def contador(t):
            llamadas["n"] += 1
            return original(t)

        monkeypatch.setattr(bd, "lemmatize", contador)
        bd._build_block_patterns(pares, "diagnoses", 3, str(tmp_path), claves, 1.0)
        assert llamadas["n"] == 0  # segunda vez sale todo de la caché


class TestLoadDiagnoses:
    pytestmark = pytest.mark.usefixtures("lemmatize_identidad")

    def test_agrupa_por_bloque_de_tres_caracteres(self, tmp_path):
        csv = tmp_path / "diag.csv"
        csv.write_text("code,description\nA01.0,Fiebre tifoidea\nB012,Varicela\n", encoding="utf-8")
        resultado = bd.load_diagnoses(str(csv), 3, None)
        assert set(resultado) == {"A01", "B01"}

    def test_expande_las_alternativas_separadas_por_barra(self, tmp_path):
        csv = tmp_path / "diag.csv"
        csv.write_text("code,description\nA00,Cólera | Infección por Vibrio\n", encoding="utf-8")
        resultado = bd.load_diagnoses(str(csv), 3, None)
        assert len(resultado["A00"]) >= 2


class TestLoadProcedures:
    pytestmark = pytest.mark.usefixtures("lemmatize_identidad")

    def test_combina_varias_columnas_de_descripcion(self, tmp_path):
        csv = tmp_path / "proc.csv"
        csv.write_text("code,class_name,subclass_name\n0DTJ4ZZ,Bypass,Cardiaco\n", encoding="utf-8")
        resultado = bd.load_procedures(str(csv), 3, None)
        assert "0DT" in resultado
        assert len(resultado["0DT"]) == 2  # una entrada por columna presente

    def test_columnas_ausentes_no_dan_error(self, tmp_path):
        csv = tmp_path / "proc.csv"
        csv.write_text("code,description\n0DTJ4ZZ,Bypass\n", encoding="utf-8")
        resultado = bd.load_procedures(str(csv), 3, None)
        assert "0DT" in resultado


class TestLoadChemicals:
    pytestmark = pytest.mark.usefixtures("lemmatize_identidad")

    def test_descarta_filas_sin_codigo(self, tmp_path):
        csv = tmp_path / "chem.csv"
        csv.write_text(
            "code1,description\n-,Sustancia sin clasificar\nT400,Heroína\n", encoding="utf-8"
        )
        resultado = bd.load_chemicals(str(csv), 3, None)
        assert set(resultado) == {"T40"}

    def test_usa_los_tres_primeros_caracteres_del_codigo(self, tmp_path):
        csv = tmp_path / "chem.csv"
        csv.write_text("code1,description\nT409X1A,Sobredosis de opioide\n", encoding="utf-8")
        resultado = bd.load_chemicals(str(csv), 3, None)
        assert "T40" in resultado


class TestPredictBloques:
    pytestmark = pytest.mark.usefixtures("lemmatize_identidad")

    def test_predice_el_bloque_cuyo_patron_hace_match(self):
        patrones = {"A01": [(bd.build_pattern("fiebre tifoidea"), 1.0)]}
        resultados, n_ignorados = bd.predict(
            ["paciente con fiebre tifoidea"], patrones, "test", {"A01"}
        )
        assert resultados == [["A01"]]
        assert n_ignorados == 0

    def test_cuenta_los_bloques_fuera_del_vocabulario_evaluado(self):
        patrones = {"A01": [(bd.build_pattern("fiebre tifoidea"), 1.0)]}
        resultados, n_ignorados = bd.predict(
            ["paciente con fiebre tifoidea"], patrones, "test", set()
        )
        assert resultados == [[]]
        assert n_ignorados == 1

    def test_sin_match_no_predice_nada(self):
        patrones = {"A01": [(bd.build_pattern("fiebre tifoidea"), 1.0)]}
        resultados, _ = bd.predict(["fractura de fémur"], patrones, "test", {"A01"})
        assert resultados == [[]]


def test_print_metrics_informa_de_precision_recall_y_map(capsys):
    y_true = np.array([[1, 0], [0, 1]])
    y_pred = np.array([[1, 0], [0, 0]])
    bd.print_metrics(y_true, y_pred, split="val", source="diagnoses")
    salida = capsys.readouterr().out
    assert "micro" in salida
    assert "MAP por documento" in salida


def test_print_metrics_reporta_los_ignorados_si_los_hay(capsys):
    y_true = np.array([[1]])
    y_pred = np.array([[1]])
    bd.print_metrics(y_true, y_pred, split="test", source="diagnoses", n_ignored=3)
    assert "ignorados" in capsys.readouterr().out


class TestLoadCorpus:
    pytestmark = pytest.mark.usefixtures("lemmatize_identidad")

    def _csv(self, tmp_path, filas):
        ruta = tmp_path / "train.csv"
        ruta.write_text(
            "text,labels\n" + "\n".join(f"{t},{lb}" for t, lb in filas), encoding="utf-8"
        )
        return ruta

    def test_extrae_n_gramas_por_bloque(self, tmp_path):
        csv = self._csv(
            tmp_path,
            [
                ("paciente con fiebre alta", "A01"),
                ("paciente con fiebre alta y tos", "A01"),
                ("control rutinario sin sintomas", "B02"),
            ],
        )
        bloques, _ = bd.load_corpus(
            str(csv),
            min_len=3,
            cache_dir=None,
            min_freq=1,
            min_precision=0.5,
            ngram_min=2,
            ngram_max=2,
        )
        assert set(bloques) == {"A01", "B02"}
        assert any(p.search("fiebre alta") for p, _ in bloques["A01"])

    def test_un_ngrama_compartido_va_al_bloque_con_mejor_puntuacion(self, tmp_path):
        # "sintoma comun" aparece en las tres notas, pero con más frecuencia en A01.
        csv = self._csv(
            tmp_path,
            [
                ("sintoma comun mas fiebre", "A01"),
                ("sintoma comun mas tos", "A01"),
                ("sintoma comun solamente", "B02"),
            ],
        )
        bloques, _ = bd.load_corpus(
            str(csv),
            min_len=3,
            cache_dir=None,
            min_freq=1,
            min_precision=0.3,
            ngram_min=2,
            ngram_max=2,
            exclusive=True,
        )
        patrones_b02 = [p.pattern for p, _ in bloques.get("B02", [])]
        assert not any("sintoma" in p for p in patrones_b02)

    def test_max_patterns_limita_los_patrones_por_bloque(self, tmp_path):
        csv = self._csv(
            tmp_path,
            [
                ("uno dos tres cuatro cinco seis", "A01"),
                ("uno dos tres cuatro cinco seis", "A01"),
            ],
        )
        bloques, top = bd.load_corpus(
            str(csv),
            min_len=1,
            cache_dir=None,
            min_freq=1,
            min_precision=0.5,
            ngram_min=2,
            ngram_max=2,
            max_patterns=1,
        )
        assert len(bloques["A01"]) == 1
        assert len(top["A01"]) == 1

    def test_usa_la_cache_en_la_segunda_llamada(self, tmp_path, monkeypatch):
        csv = self._csv(tmp_path, [("paciente con fiebre alta", "A01")])
        cache_dir = str(tmp_path / "cache")
        bd.load_corpus(
            str(csv),
            min_len=3,
            cache_dir=cache_dir,
            min_freq=1,
            min_precision=0.5,
            ngram_min=2,
            ngram_max=2,
        )
        llamadas = {"n": 0}
        original = bd.lemmatize

        def contador(t):
            llamadas["n"] += 1
            return original(t)

        monkeypatch.setattr(bd, "lemmatize", contador)
        bd.load_corpus(
            str(csv),
            min_len=3,
            cache_dir=cache_dir,
            min_freq=1,
            min_precision=0.5,
            ngram_min=2,
            ngram_max=2,
        )
        assert llamadas["n"] == 0

    def test_reutiliza_los_lemas_de_las_notas_aunque_cambien_los_umbrales(
        self, tmp_path, monkeypatch
    ):
        """La caché de lemas depende del fichero, no de min_freq/min_precision."""
        csv = self._csv(tmp_path, [("paciente con fiebre alta", "A01")])
        cache_dir = str(tmp_path / "cache")
        bd.load_corpus(
            str(csv),
            min_len=3,
            cache_dir=cache_dir,
            min_freq=1,
            min_precision=0.5,
            ngram_min=2,
            ngram_max=2,
        )
        llamadas = {"n": 0}
        original = bd.lemmatize

        def contador(t):
            llamadas["n"] += 1
            return original(t)

        monkeypatch.setattr(bd, "lemmatize", contador)
        bd.load_corpus(
            str(csv),
            min_len=3,
            cache_dir=cache_dir,
            min_freq=2,
            min_precision=0.9,
            ngram_min=2,
            ngram_max=2,
        )
        assert llamadas["n"] == 0

    def test_min_freq_descarta_ngramas_poco_frecuentes(self, tmp_path):
        csv = self._csv(
            tmp_path,
            [("evento raro una vez", "A01"), ("otra nota distinta del todo", "A01")],
        )
        bloques, _ = bd.load_corpus(
            str(csv),
            min_len=1,
            cache_dir=None,
            min_freq=2,
            min_precision=0.1,
            ngram_min=2,
            ngram_max=2,
        )
        assert bloques == {}  # ningún bigrama se repite dos veces

    def test_min_precision_descarta_ngramas_poco_discriminativos(self, tmp_path):
        # "nota de" aparece en las dos notas, en bloques distintos: precisión 0.5.
        # "de control" solo aparece en la nota de A01: precisión 1.0.
        csv = self._csv(
            tmp_path,
            [("nota de control", "A01"), ("nota de seguimiento", "B02")],
        )
        bloques, _ = bd.load_corpus(
            str(csv),
            min_len=1,
            cache_dir=None,
            min_freq=1,
            min_precision=0.9,
            ngram_min=2,
            ngram_max=2,
        )
        patrones_a01 = [p.pattern for p, _ in bloques.get("A01", [])]
        assert bd.build_pattern("nota de").pattern not in patrones_a01
        assert bd.build_pattern("de control").pattern in patrones_a01


class TestLoadClinical:
    pytestmark = pytest.mark.usefixtures("lemmatize_identidad")

    def _task_x(self, tmp_path, filas, nombre="task_x.csv"):
        import csv as csv_mod

        ruta = tmp_path / nombre
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            writer = csv_mod.writer(f)
            writer.writerow(["task_x"])
            for anotaciones in filas:
                writer.writerow([repr(anotaciones)])
        return ruta

    def test_extrae_terminos_anotados_por_bloque(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bd, "build_synonym_map", lambda terms, **kw: {})
        ruta = self._task_x(tmp_path, [[{"code": "A01.0", "text": "fiebre tifoidea"}]])
        resultado = bd.load_clinical([str(ruta)], min_len=3, cache_dir=None)
        assert "A01" in resultado
        assert resultado["A01"][0][0].search("fiebre tifoidea")
        assert resultado["A01"][0][1] == bd.CONF_CLINICAL_ORIGINAL

    def test_terminos_mas_cortos_que_min_len_se_descartan(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bd, "build_synonym_map", lambda terms, **kw: {})
        ruta = self._task_x(tmp_path, [[{"code": "A01.0", "text": "tos"}]])
        resultado = bd.load_clinical([str(ruta)], min_len=10, cache_dir=None)
        assert resultado == {}

    def test_una_fila_con_task_x_ilegible_se_ignora(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bd, "build_synonym_map", lambda terms, **kw: {})
        ruta = tmp_path / "task_x.csv"
        ruta.write_text("task_x\nesto no es una lista de python\n", encoding="utf-8")
        assert bd.load_clinical([str(ruta)], min_len=3, cache_dir=None) == {}

    def test_los_sinonimos_generan_variantes_con_menor_confianza(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            bd, "build_synonym_map", lambda terms, **kw: {"fiebre": ["temperatura"]}
        )
        ruta = self._task_x(tmp_path, [[{"code": "A01.0", "text": "fiebre alta"}]])
        resultado = bd.load_clinical([str(ruta)], min_len=3, cache_dir=None)
        confianzas = {c for _, c in resultado["A01"]}
        assert bd.CONF_CLINICAL_ORIGINAL in confianzas
        assert bd.CONF_CLINICAL_SYNONYM in confianzas

    def test_usa_la_cache_de_patrones_en_la_segunda_llamada(self, tmp_path, monkeypatch):
        # build_synonym_map tiene su propia caché (ya probada en TestBuildSynonymMap);
        # aquí se comprueba la caché de patrones, así que se sustituye por algo fijo.
        monkeypatch.setattr(bd, "build_synonym_map", lambda terms, **kw: {})
        llamadas = {"n": 0}
        original = bd.expand_term

        def contador(term, syn_map):
            llamadas["n"] += 1
            return original(term, syn_map)

        monkeypatch.setattr(bd, "expand_term", contador)
        ruta = self._task_x(tmp_path, [[{"code": "A01.0", "text": "fiebre tifoidea"}]])
        cache_dir = str(tmp_path / "cache")
        bd.load_clinical([str(ruta)], min_len=3, cache_dir=cache_dir)
        assert llamadas["n"] == 1
        bd.load_clinical([str(ruta)], min_len=3, cache_dir=cache_dir)
        assert llamadas["n"] == 1  # la segunda llamada sale de la caché de patrones
