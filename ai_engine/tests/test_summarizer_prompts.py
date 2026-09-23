"""
Tests de la construcción de prompts del resumidor.

Cada familia de modelos espera su propio formato de conversación, y equivocarlo no produce
un error: produce un resumen peor, con el modelo respondiendo a un texto que interpreta como
parte del informe. Por eso conviene fijar los formatos.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from summarizer import MODELS, _build_prompt, _fallback_summary


class TestFormatoDeCadaModelo:
    @pytest.mark.parametrize("modelo", ["gemma3", "gemma4", "gemma4-2b"])
    def test_gemma_usa_sus_marcas_de_turno(self, modelo):
        p = _build_prompt(modelo, "summary", "informe", "sistema", "usuario {text}")
        assert p.startswith("<start_of_turn>user")
        assert p.rstrip().endswith("<start_of_turn>model")

    @pytest.mark.parametrize("modelo", ["phi4", "qwen"])
    def test_phi_y_qwen_usan_el_formato_chatml(self, modelo):
        p = _build_prompt(modelo, "summary", "informe", "sistema", "usuario {text}")
        assert "<|im_start|>system" in p
        assert p.rstrip().endswith("<|im_start|>assistant")

    def test_un_modelo_desconocido_cae_a_texto_plano(self):
        p = _build_prompt("modelo-raro", "summary", "informe", "sistema", "usuario {text}")
        assert "<start_of_turn>" not in p
        assert "<|im_start|>" not in p
        assert "sistema" in p


class TestInterpolacion:
    def test_el_informe_sustituye_al_marcador(self):
        p = _build_prompt("gemma4", "summary", "paciente con disnea", "s", "Informe: {text}")
        assert "paciente con disnea" in p
        assert "{text}" not in p

    def test_una_variable_sin_rellenar_no_rompe_nada(self):
        """El admin puede dejar {language} en el prompt: con str.format esto reventaría."""
        p = _build_prompt("gemma4", "summary", "informe", "Responde en {language}", "{text}")
        assert "{language}" in p

    def test_las_llaves_del_informe_no_se_interpretan(self):
        p = _build_prompt("gemma4", "summary", "dosis {1,2}", "s", "{text}")
        assert "dosis {1,2}" in p

    def test_el_prompt_de_sistema_va_antes_que_el_del_usuario(self):
        p = _build_prompt("gemma4", "summary", "t", "SISTEMA", "USUARIO {text}")
        assert p.index("SISTEMA") < p.index("USUARIO")


class TestRespaldoSinModelo:
    def test_describe_el_informe_por_su_tamano(self):
        assert "3 palabras" in _fallback_summary("uno dos tres")

    def test_un_texto_vacio_no_rompe(self):
        assert "0 palabras" in _fallback_summary("")

    def test_el_respaldo_no_inventa_contenido_clinico(self):
        """Sin modelo cargado se dice que se procesó, no se resume: fabricar un resumen
        clínico falso sería peor que no dar ninguno."""
        salida = _fallback_summary("paciente con neumonía bilateral y fiebre alta")
        assert "neumonía" not in salida


class TestCatalogoDeModelos:
    def test_los_modelos_declarados_traen_repositorio_y_fichero(self):
        for clave, meta in MODELS.items():
            assert meta.get("repo"), clave
            assert meta.get("filename", "").endswith(".gguf"), clave
            assert meta.get("display"), clave

    def test_hay_al_menos_un_modelo_disponible(self):
        assert len(MODELS) >= 1
