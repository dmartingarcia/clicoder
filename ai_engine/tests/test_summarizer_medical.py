"""Tests de MedicalSummarizer y create_summarizer(): validación, carga y generación."""

import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import summarizer as summarizer_module
from summarizer import MedicalSummarizer, create_summarizer

SISTEMA = "Eres un asistente médico."
USUARIO = "Resume: {text}"


class TestValidacionInit:
    def test_modelo_desconocido_es_un_error(self):
        with pytest.raises(ValueError, match="ERR_INVALID_MODEL"):
            MedicalSummarizer("modelo-inventado", "summary", SISTEMA, USUARIO)

    def test_modo_desconocido_es_un_error(self):
        with pytest.raises(ValueError, match="ERR_INVALID_MODE"):
            MedicalSummarizer("gemma3", "modo-raro", SISTEMA, USUARIO)

    def test_sin_prompt_de_sistema_es_un_error(self):
        with pytest.raises(ValueError, match="ERR_MISSING_SYSTEM_PROMPT"):
            MedicalSummarizer("gemma3", "summary", "  ", USUARIO)

    def test_sin_prompt_de_usuario_es_un_error(self):
        with pytest.raises(ValueError, match="ERR_MISSING_USER_PROMPT"):
            MedicalSummarizer("gemma3", "summary", SISTEMA, "")

    def test_prompt_de_usuario_sin_marcador_es_un_error(self):
        with pytest.raises(ValueError, match="ERR_USER_PROMPT_MISSING_PLACEHOLDER"):
            MedicalSummarizer("gemma3", "summary", SISTEMA, "sin marcador aqui")

    def test_construccion_valida_expone_sus_propiedades(self):
        s = MedicalSummarizer("gemma3", "summary", SISTEMA, USUARIO)
        assert s.model_name == "Gemma 3 4B IT"
        assert s.mode == "summary"
        assert s.is_loaded is False  # todavía no se ha llamado a load()


class TestUpdatePrompts:
    def test_actualiza_los_prompts_sin_recargar(self):
        s = MedicalSummarizer("gemma3", "summary", SISTEMA, USUARIO)
        s.update_prompts("Nuevo sistema", "Nuevo usuario {text}")
        assert s._system_prompt == "Nuevo sistema"
        assert s._user_prompt == "Nuevo usuario {text}"

    def test_rechaza_prompt_de_sistema_vacio(self):
        s = MedicalSummarizer("gemma3", "summary", SISTEMA, USUARIO)
        with pytest.raises(ValueError, match="ERR_MISSING_SYSTEM_PROMPT"):
            s.update_prompts("", USUARIO)

    def test_rechaza_prompt_de_usuario_vacio(self):
        s = MedicalSummarizer("gemma3", "summary", SISTEMA, USUARIO)
        with pytest.raises(ValueError, match="ERR_MISSING_USER_PROMPT"):
            s.update_prompts(SISTEMA, "")

    def test_rechaza_prompt_sin_marcador(self):
        s = MedicalSummarizer("gemma3", "summary", SISTEMA, USUARIO)
        with pytest.raises(ValueError, match="ERR_USER_PROMPT_MISSING_PLACEHOLDER"):
            s.update_prompts(SISTEMA, "sin marcador")


class TestLoad:
    def test_carga_el_modelo_cuando_llama_cpp_esta_disponible(self, monkeypatch):
        s = MedicalSummarizer("gemma3", "summary", SISTEMA, USUARIO)
        monkeypatch.setattr(s, "_ensure_downloaded", lambda: Path("/tmp/falso.gguf"))

        class LlamaFalso:
            def __init__(self, **kw):
                self.kw = kw

        modulo_falso = type("mod", (), {"Llama": LlamaFalso})
        monkeypatch.setitem(sys.modules, "llama_cpp", modulo_falso)

        s.load()
        assert s.is_loaded is True

    def test_sin_llama_cpp_instalado_da_un_error_con_solucion(self, monkeypatch):
        s = MedicalSummarizer("gemma3", "summary", SISTEMA, USUARIO)
        monkeypatch.setattr(s, "_ensure_downloaded", lambda: Path("/tmp/falso.gguf"))
        monkeypatch.setitem(sys.modules, "llama_cpp", None)  # fuerza ImportError

        with pytest.raises(RuntimeError, match="pip install llama-cpp-python"):
            s.load()


class TestEnsureDownloaded:
    def test_sin_huggingface_hub_da_un_error_con_solucion(self, monkeypatch):
        s = MedicalSummarizer("gemma3", "summary", SISTEMA, USUARIO)
        monkeypatch.setitem(sys.modules, "huggingface_hub", None)
        with pytest.raises(RuntimeError, match="pip install huggingface-hub"):
            s._ensure_downloaded()

    def test_usa_el_fichero_cacheado_sin_relanzar_la_descarga(self, monkeypatch, tmp_path):
        import huggingface_hub
        from huggingface_hub import constants as hf_constants

        monkeypatch.setattr(hf_constants, "HF_HUB_CACHE", str(tmp_path))
        s = MedicalSummarizer("gemma3", "summary", SISTEMA, USUARIO)

        blobs = tmp_path / f"models--{s._cfg['repo'].replace('/', '--')}" / "blobs"
        blobs.mkdir(parents=True)
        (blobs / "peso").write_bytes(b"x")

        # Se falsea solo el tamaño (evita escribir 2,5 GB reales); el resto de
        # stat() pasa intacto para que is_file() se siga resolviendo bien.
        stat_real = Path.stat

        class _StatConTamanoFalso:
            def __init__(self, original):
                self._original = original

            def __getattr__(self, nombre):
                return getattr(self._original, nombre)

            @property
            def st_size(self):
                return 10**12

        monkeypatch.setattr(Path, "stat", lambda self: _StatConTamanoFalso(stat_real(self)))

        llamadas = []
        monkeypatch.setattr(
            huggingface_hub,
            "hf_hub_download",
            lambda **kw: llamadas.append(kw) or str(tmp_path / "modelo.gguf"),
        )
        ruta = s._ensure_downloaded()
        assert ruta == tmp_path / "modelo.gguf"
        assert llamadas[0]["repo_id"] == s._cfg["repo"]

    def test_sin_cache_lanza_la_descarga_y_el_hilo_de_progreso(self, monkeypatch, tmp_path):
        import huggingface_hub
        from huggingface_hub import constants as hf_constants

        monkeypatch.setattr(hf_constants, "HF_HUB_CACHE", str(tmp_path))
        s = MedicalSummarizer("gemma3", "summary", SISTEMA, USUARIO)

        monkeypatch.setattr(
            huggingface_hub, "hf_hub_download", lambda **kw: str(tmp_path / "modelo.gguf")
        )
        ruta = s._ensure_downloaded()
        assert ruta == tmp_path / "modelo.gguf"


class TestSummarize:
    def _cargado(self, mode="summary"):
        s = MedicalSummarizer("gemma3", mode, SISTEMA, USUARIO)
        s._llm = lambda *a, **kw: None  # se sobreescribe por test; marca is_loaded=True
        return s

    def test_llama_a_load_si_no_esta_cargado(self, monkeypatch):
        s = MedicalSummarizer("gemma3", "summary", SISTEMA, USUARIO)
        llamado = {"n": 0}

        def load_falso():
            llamado["n"] += 1
            s._llm = lambda *a, **kw: {"choices": [{"text": "resumen"}]}

        monkeypatch.setattr(s, "load", load_falso)
        s.summarize("texto de prueba")
        assert llamado["n"] == 1

    def test_recorta_el_texto_de_entrada_por_encima_del_limite(self):
        s = self._cargado("summary")
        capturado = {}

        def llm_falso(prompt, **kw):
            capturado["prompt"] = prompt
            return {"choices": [{"text": "ok"}]}

        s._llm = llm_falso
        texto_largo = " ".join(f"palabra{i}" for i in range(700))  # > 600, límite de "summary"
        s.summarize(texto_largo)
        assert "palabra699" not in capturado["prompt"]

    def test_quita_el_prefijo_habitual_de_la_respuesta(self):
        s = self._cargado()
        s._llm = lambda *a, **kw: {"choices": [{"text": "Resumen médico: paciente estable"}]}
        assert s.summarize("texto") == "paciente estable"

    def test_respuesta_vacia_cae_al_resumen_estadistico(self):
        s = self._cargado()
        s._llm = lambda *a, **kw: {"choices": [{"text": "   "}]}
        assert "palabras procesado" in s.summarize("una dos tres")


class TestSummarizeStream:
    def test_generador_produce_los_fragmentos_del_llm(self):
        s = MedicalSummarizer("gemma3", "summary", SISTEMA, USUARIO)

        def llm_falso(prompt, **kw):
            return iter(
                [
                    {"choices": [{"text": "Hola"}]},
                    {"choices": [{"text": ""}]},  # fragmento vacío: no debe emitirse
                    {"choices": [{"text": " mundo"}]},
                ]
            )

        s._llm = llm_falso
        tokens = list(s.summarize_stream("texto de prueba"))
        assert tokens == ["Hola", " mundo"]

    def test_usa_los_prompts_de_la_peticion_si_se_pasan(self):
        """El backend puede pre-rellenar prompts sin placeholders para esta petición
        concreta, sin tocar los que quedan guardados en el summarizer."""
        s = MedicalSummarizer("gemma3", "summary", SISTEMA, USUARIO)
        capturado = {}

        def llm_falso(prompt, **kw):
            capturado["prompt"] = prompt
            return iter([{"choices": [{"text": "x"}]}])

        s._llm = llm_falso
        list(
            s.summarize_stream(
                "texto", system_prompt="Sistema override", user_prompt="Usuario override {text}"
            )
        )
        assert "Sistema override" in capturado["prompt"]
        assert s._system_prompt == SISTEMA  # el prompt guardado no cambia

    def test_llama_a_load_si_no_esta_cargado(self, monkeypatch):
        s = MedicalSummarizer("gemma3", "summary", SISTEMA, USUARIO)
        llamado = {"n": 0}

        def load_falso():
            llamado["n"] += 1
            s._llm = lambda *a, **kw: iter([{"choices": [{"text": "x"}]}])

        monkeypatch.setattr(s, "load", load_falso)
        list(s.summarize_stream("texto"))
        assert llamado["n"] == 1

    def test_recorta_el_texto_de_entrada_por_encima_del_limite(self):
        s = MedicalSummarizer("gemma3", "summary", SISTEMA, USUARIO)
        capturado = {}

        def llm_falso(prompt, **kw):
            capturado["prompt"] = prompt
            return iter([{"choices": [{"text": "x"}]}])

        s._llm = llm_falso
        texto_largo = " ".join(f"palabra{i}" for i in range(700))
        list(s.summarize_stream(texto_largo))
        assert "palabra699" not in capturado["prompt"]


def test_watch_gguf_download_termina_al_marcar_el_evento(tmp_path):
    stop = threading.Event()
    hilo = threading.Thread(
        target=summarizer_module._watch_gguf_download,
        args=("org/repo", "modelo.gguf", 100.0, tmp_path, stop),
    )
    hilo.start()
    time.sleep(0.05)
    stop.set()
    hilo.join(timeout=2)
    assert not hilo.is_alive()


@pytest.mark.parametrize("total_mb", [100.0, 0.0])
def test_watch_gguf_download_reporta_progreso_si_hay_blobs(tmp_path, total_mb):
    blobs = tmp_path / "models--org--repo" / "blobs"
    blobs.mkdir(parents=True)
    (blobs / "peso.bin").write_bytes(b"0" * 1024 * 1024)
    stop = threading.Event()
    hilo = threading.Thread(
        target=summarizer_module._watch_gguf_download,
        args=("org/repo", "modelo.gguf", total_mb, tmp_path, stop),
    )
    hilo.start()
    time.sleep(0.05)
    stop.set()
    hilo.join(timeout=2)
    assert not hilo.is_alive()


class TestCreateSummarizer:
    def test_por_defecto_esta_desactivado(self, monkeypatch):
        monkeypatch.delenv("SUMMARIZER_MODEL", raising=False)
        assert create_summarizer() is None

    def test_none_explicito_desactiva(self, monkeypatch):
        monkeypatch.setenv("SUMMARIZER_MODEL", "none")
        assert create_summarizer() is None

    def test_modelo_no_reconocido_desactiva_en_vez_de_fallar(self, monkeypatch):
        monkeypatch.setenv("SUMMARIZER_MODEL", "modelo-que-no-existe")
        assert create_summarizer() is None

    def test_modo_no_reconocido_usa_summary_por_defecto(self, monkeypatch):
        monkeypatch.setenv("SUMMARIZER_MODEL", "gemma3")
        monkeypatch.setenv("SUMMARIZER_MODE", "modo-raro")
        s = create_summarizer()
        assert s.mode == "summary"

    def test_modelo_valido_construye_el_summarizer(self, monkeypatch):
        monkeypatch.setenv("SUMMARIZER_MODEL", "qwen")
        monkeypatch.delenv("SUMMARIZER_MODE", raising=False)
        s = create_summarizer()
        assert s.model_name == "Qwen 2.5 3B Instruct"

    def test_sin_prompts_en_el_entorno_usa_los_prompts_por_defecto(self, monkeypatch):
        monkeypatch.setenv("SUMMARIZER_MODEL", "gemma3")
        monkeypatch.delenv("SUMMARIZER_SYSTEM_PROMPT", raising=False)
        monkeypatch.delenv("SUMMARIZER_USER_PROMPT", raising=False)
        s = create_summarizer()
        assert "{text}" in s._user_prompt

    def test_el_modo_paraphrase_usa_sus_propios_prompts_por_defecto(self, monkeypatch):
        monkeypatch.setenv("SUMMARIZER_MODEL", "gemma3")
        monkeypatch.setenv("SUMMARIZER_MODE", "paraphrase")
        monkeypatch.delenv("SUMMARIZER_SYSTEM_PROMPT", raising=False)
        monkeypatch.delenv("SUMMARIZER_USER_PROMPT", raising=False)
        s = create_summarizer()
        assert "reformula" in s._user_prompt.lower()

    def test_los_prompts_del_entorno_tienen_prioridad_sobre_los_por_defecto(self, monkeypatch):
        monkeypatch.setenv("SUMMARIZER_MODEL", "gemma3")
        monkeypatch.setenv("SUMMARIZER_SYSTEM_PROMPT", "Sistema custom")
        monkeypatch.setenv("SUMMARIZER_USER_PROMPT", "Usuario custom {text}")
        s = create_summarizer()
        assert s._system_prompt == "Sistema custom"
