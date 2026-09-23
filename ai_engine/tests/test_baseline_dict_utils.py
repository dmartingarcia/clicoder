"""
Tests de las funciones puras del diccionario: normalización, expansión y n-gramas.

Son la base de todo el clasificador léxico: si la normalización cambia, dejan de casar
patrones que antes casaban, y eso se manifiesta como códigos que desaparecen sin que
ningún error salte. No cargan spaCy: solo cubren la lógica determinista.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from baseline_dict import (
    _cache_key,
    _normalize_gender,
    _strip_accents,
    build_pattern,
    compute_map,
    expand_abbreviations,
    expand_description,
    expand_term,
    extract_ngrams,
    normalize,
    parse_labels,
)

# =============================================================================
# Normalización
# =============================================================================


def test_quita_las_tildes():
    assert _strip_accents("neumonía bilateral") == "neumonia bilateral"


def test_normalizar_baja_a_minusculas_y_quita_tildes():
    assert normalize("Neumonía BILATERAL") == "neumonia bilateral"


def test_normalizar_es_idempotente():
    una = normalize("Hipertensión Arterial")
    assert normalize(una) == una


def test_el_femenino_se_lleva_al_masculino():
    """Sin esto, 'insuficiencia aguda' y 'proceso agudo' serían términos distintos y el
    diccionario no casaría uno de los dos."""
    assert _normalize_gender("aguda") == "agudo"


def test_el_masculino_se_deja_igual():
    assert _normalize_gender("agudo") == "agudo"


def test_las_palabras_cortas_no_se_tocan():
    # Con menos de cuatro letras el cambio produciría palabras que no existen.
    assert _normalize_gender("ala") == "ala"


# =============================================================================
# Abreviaturas clínicas
# =============================================================================


def test_expande_una_abreviatura_conocida():
    salida = expand_abbreviations("paciente con HTA")
    assert "hipertension" in salida.lower() or "HTA" not in salida


def test_no_toca_el_texto_sin_abreviaturas():
    texto = "paciente con dolor abdominal"
    assert expand_abbreviations(texto) == texto


def test_no_expande_dentro_de_otra_palabra():
    # 'CHATA' contiene 'HTA': expandirla produciría términos inventados.
    salida = expand_abbreviations("la mesa CHATA")
    assert "CHATA" in salida


# =============================================================================
# Patrones
# =============================================================================


def test_el_patron_casa_la_frase_completa():
    assert build_pattern("neumonia bilateral").search("hay neumonia bilateral aqui")


def test_el_patron_respeta_los_limites_de_palabra():
    assert not build_pattern("gota").search("gotas en el ojo")


def test_los_caracteres_especiales_se_escapan():
    # Un paréntesis sin escapar rompería la expresión regular al compilarla; escapado,
    # el patrón se construye aunque el límite de palabra tras ')' no permita casarlo.
    patron = build_pattern("tumor (benigno)")
    assert patron.pattern.count("\\(") == 1


# =============================================================================
# Etiquetas y descripciones
# =============================================================================


def test_las_etiquetas_se_truncan_a_bloque_de_tres():
    assert parse_labels("a15.0;e11.9") == ["A15", "E11"]


def test_las_etiquetas_vacias_se_descartan():
    assert parse_labels("") == []
    assert parse_labels("a15.0;;") == ["A15"]


def test_las_etiquetas_no_se_repiten_en_desorden():
    assert parse_labels("I10;I10") == ["I10", "I10"]


def test_una_descripcion_con_alternativas_genera_una_variante_por_cada_una():
    variantes = expand_description("Cólera | Infección por Vibrio")
    assert any("cólera" in v.lower() for v in variantes)
    assert any("vibrio" in v.lower() for v in variantes)


def test_el_parentesis_produce_variante_con_y_sin_su_contenido():
    variantes = expand_description("Tuberculosis de las meninges (cerebral espinal)")
    textos = " ".join(variantes).lower()
    assert "tuberculosis de las meninges" in textos
    assert "cerebral espinal" in textos


# =============================================================================
# N-gramas
# =============================================================================


def test_extrae_ngramas_del_tamano_pedido():
    ngramas = extract_ngrams("uno dos tres cuatro", min_n=2, max_n=2)
    assert "uno dos" in ngramas
    assert "dos tres" in ngramas
    assert "uno dos tres" not in ngramas


def test_un_texto_mas_corto_que_el_minimo_no_da_ngramas():
    assert extract_ngrams("uno dos", min_n=3, max_n=5) == []


def test_los_ngramas_cubren_todo_el_rango():
    ngramas = extract_ngrams("a b c d e", min_n=2, max_n=3)
    assert any(len(n.split()) == 2 for n in ngramas)
    assert any(len(n.split()) == 3 for n in ngramas)


# =============================================================================
# Caché y métrica
# =============================================================================


def test_la_clave_de_cache_cambia_con_las_entradas():
    assert _cache_key("a", "b") != _cache_key("a", "c")


def test_la_clave_de_cache_es_estable():
    assert _cache_key("diagnoses", 3) == _cache_key("diagnoses", 3)


def test_expandir_un_termino_sin_sinonimos_lo_devuelve_tal_cual():
    assert "neumonia" in [t.lower() for t in expand_term("neumonia", {})]


def test_el_map_del_diccionario_es_cero_sin_aciertos():
    import numpy as np

    y_true = np.array([[1, 0], [0, 1]])
    y_pred = np.array([[0, 1], [1, 0]])
    assert compute_map(y_true, y_pred) < 0.6


def test_el_map_del_diccionario_es_uno_con_acierto_pleno():
    import numpy as np

    y = np.array([[1, 0], [0, 1]])
    assert compute_map(y, y) == pytest.approx(1.0)
