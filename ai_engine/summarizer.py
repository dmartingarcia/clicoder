"""
summarizer.py — Resumen médico de informes clínicos via LLM local (GGUF/llama-cpp).

Variables de entorno
--------------------
SUMMARIZER_MODEL   Modelo a usar: "gemma3" | "gemma4" | "gemma4-2b" | "phi4" | "qwen" | "none" (default: "none").
                   Con "none" se devuelve el resumen estadístico básico.
SUMMARIZER_MODE    Modo de salida: "summary" | "paraphrase" (default: "summary").
                   - summary:    resumen conciso de ~120 palabras.
                   - paraphrase: reformulación completa estructurada por secciones,
                                 conservando todos los detalles médicos.
SUMMARIZER_THREADS Número de hilos CPU para llama-cpp (default: 4).
SUMMARIZER_CTX     Tamaño de contexto en tokens (default: 8192).
"""

import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger("cie10_engine")

# ─────────────────────────────────────────────
# Catálogo de modelos soportados
# ─────────────────────────────────────────────

MODELS = {
    "gemma3": {
        "repo": "ggml-org/gemma-3-4b-it-GGUF",
        "filename": "gemma-3-4b-it-Q4_K_M.gguf",
        "display": "Gemma 3 4B IT",
        "size_gb": 2.5,
    },
    "gemma4": {
        "repo": "ggml-org/gemma-4-E4B-it-GGUF",
        "filename": "gemma-4-E4B-it-Q4_K_M.gguf",
        "display": "Gemma 4 E4B IT",
        "size_gb": 2.5,
    },
    "gemma4-2b": {
        "repo": "ggml-org/gemma-4-E2B-it-GGUF",
        "filename": "gemma-4-E2B-it-Q4_K_M.gguf",
        "display": "Gemma 4 E2B IT",
        "size_gb": 1.3,
    },
    "phi4": {
        "repo": "bartowski/microsoft_Phi-4-mini-instruct-GGUF",
        "filename": "microsoft_Phi-4-mini-instruct-Q4_K_M.gguf",
        "display": "Phi-4 Mini Instruct",
        "size_gb": 2.4,
    },
    "qwen": {
        "repo": "Qwen/Qwen2.5-3B-Instruct-GGUF",
        "filename": "qwen2.5-3b-instruct-q4_k_m.gguf",
        "display": "Qwen 2.5 3B Instruct",
        "size_gb": 2.0,
    },
}

# ─────────────────────────────────────────────
# Prompts por modo
# ─────────────────────────────────────────────

MODES = ("summary", "paraphrase")


class MedicalSummarizer:
    """Genera resúmenes o paráfrasis médicas usando un LLM local en formato GGUF."""

    def __init__(
        self, model_key: str, mode: str = "summary", system_prompt: str = "", user_prompt: str = ""
    ):
        if model_key not in MODELS:
            raise ValueError(f"ERR_INVALID_MODEL:{model_key}")
        if mode not in MODES:
            raise ValueError(f"ERR_INVALID_MODE:{mode}")
        if not system_prompt or not system_prompt.strip():
            raise ValueError("ERR_MISSING_SYSTEM_PROMPT")
        if not user_prompt or not user_prompt.strip():
            raise ValueError("ERR_MISSING_USER_PROMPT")
        if "{text}" not in user_prompt:
            raise ValueError("ERR_USER_PROMPT_MISSING_PLACEHOLDER")
        self._model_key = model_key
        self._mode = mode
        self._cfg = MODELS[model_key]
        self._llm = None
        self._n_threads = int(os.environ.get("SUMMARIZER_THREADS", "4"))
        self._n_ctx = int(os.environ.get("SUMMARIZER_CTX", "8192"))
        self._system_prompt = system_prompt
        self._user_prompt = user_prompt

    # ── Propiedades públicas ───────────────────────────────────────────────

    @property
    def model_name(self) -> str:
        return self._cfg["display"]

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def is_loaded(self) -> bool:
        return self._llm is not None

    # ── Carga / descarga ───────────────────────────────────────────────────

    def update_prompts(self, system_prompt: str, user_prompt: str) -> None:
        """Actualiza los prompts sin recargar el modelo."""
        if not system_prompt or not system_prompt.strip():
            raise ValueError("ERR_MISSING_SYSTEM_PROMPT")
        if not user_prompt or not user_prompt.strip():
            raise ValueError("ERR_MISSING_USER_PROMPT")
        if "{text}" not in user_prompt:
            raise ValueError("ERR_USER_PROMPT_MISSING_PLACEHOLDER")
        self._system_prompt = system_prompt
        self._user_prompt = user_prompt

    def load(self) -> None:
        """Descarga (si es necesario) y carga el modelo en memoria."""
        model_path = self._ensure_downloaded()
        logger.info(
            "Cargando %s (%s) con %d hilos …",
            self._cfg["display"],
            model_path.name,
            self._n_threads,
        )
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise RuntimeError(
                "llama-cpp-python no está instalado. Instálalo con: pip install llama-cpp-python"
            ) from exc

        self._llm = Llama(
            model_path=str(model_path),
            n_ctx=self._n_ctx,
            n_threads=self._n_threads,
            verbose=False,
        )
        logger.info("%s cargado correctamente.", self._cfg["display"])

    def _ensure_downloaded(self) -> Path:
        """Devuelve la ruta local del GGUF, descargándolo si no existe."""
        try:
            from huggingface_hub import constants as hf_c
            from huggingface_hub import hf_hub_download
        except ImportError as exc:
            raise RuntimeError(
                "huggingface-hub no está instalado. Instálalo con: pip install huggingface-hub"
            ) from exc

        cache_root = Path(hf_c.HF_HUB_CACHE)
        repo = self._cfg["repo"]
        filename = self._cfg["filename"]
        size_gb = self._cfg["size_gb"]
        size_mb = size_gb * 1024

        logger.info(
            "Resumidor: preparando %s — %s (~%.1f GB) …",
            self._cfg["display"],
            filename,
            size_gb,
        )

        # Comprobamos si ya está en caché antes de lanzar el watcher
        safe_repo = repo.replace("/", "--")
        model_blob_dir = cache_root / f"models--{safe_repo}" / "blobs"
        already_cached = (
            model_blob_dir.exists()
            and any(
                f.stat().st_size > size_mb * 0.9 * 1024 * 1024
                for f in model_blob_dir.iterdir()
                if f.is_file() and not f.name.endswith(".incomplete")
            )
            if model_blob_dir.exists()
            else False
        )

        if already_cached:
            logger.info("Resumidor: %s encontrado en caché.", filename)
        else:
            logger.info(
                "Resumidor: descargando %s (~%.1f GB) — esto puede tardar varios minutos …",
                filename,
                size_gb,
            )
            stop_event = threading.Event()
            watcher = threading.Thread(
                target=_watch_gguf_download,
                args=(repo, filename, size_mb, cache_root, stop_event),
                daemon=True,
            )
            watcher.start()

            try:
                local_path = hf_hub_download(
                    repo_id=repo,
                    filename=filename,
                    cache_dir=str(cache_root),
                )
            finally:
                stop_event.set()
                watcher.join(timeout=2)

            logger.info("Resumidor: %s descargado correctamente.", filename)
            return Path(local_path)

        local_path = hf_hub_download(
            repo_id=repo,
            filename=filename,
            cache_dir=str(cache_root),
        )
        return Path(local_path)

    # ── Inferencia ─────────────────────────────────────────────────────────

    def summarize(self, text: str, max_tokens: int | None = None) -> str:
        """Genera un resumen o paráfrasis del texto. Llama a load() si no está cargado."""
        if not self.is_loaded:
            self.load()

        words = text.split()
        max_input = 600 if self._mode == "summary" else 800
        if len(words) > max_input:
            text = " ".join(words[:max_input])

        if max_tokens is None:
            max_tokens = 250 if self._mode == "summary" else 600

        prompt = _build_prompt(
            self._model_key, self._mode, text, self._system_prompt, self._user_prompt
        )

        output = self._llm(
            prompt,
            max_tokens=max_tokens,
            temperature=0.2,
            top_p=0.9,
            repeat_penalty=1.1,
            stop=["Informe:", "\n\n\n"],
        )
        result = output["choices"][0]["text"].strip()

        for prefix in (
            "Resumen médico:",
            "Resumen:",
            "**Resumen médico:**",
            "Informe reformulado:",
            "**Informe reformulado:**",
        ):
            if result.startswith(prefix):
                result = result[len(prefix) :].strip()

        return result or _fallback_summary(text)

    def summarize_stream(
        self,
        text: str,
        max_tokens: int | None = None,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
    ):
        """Genera tokens del resumen/paráfrasis de forma incremental (generador síncrono).

        Cada yield es un fragmento de texto (string). El llamador es responsable de
        ejecutar este generador en un hilo (no bloquea el event loop de asyncio).

        Si ``system_prompt`` / ``user_prompt`` se proporcionan (pre-rellenados por el
        backend — sin placeholders), se usan en lugar de los prompts almacenados.
        """
        if not self.is_loaded:
            self.load()

        words = text.split()
        max_input = 600 if self._mode == "summary" else 800
        if len(words) > max_input:
            text = " ".join(words[:max_input])

        if max_tokens is None:
            max_tokens = 250 if self._mode == "summary" else 600

        sys_p = system_prompt if system_prompt is not None else self._system_prompt
        usr_p = user_prompt if user_prompt is not None else self._user_prompt
        prompt = _build_prompt(self._model_key, self._mode, text, sys_p, usr_p)

        for chunk in self._llm(
            prompt,
            max_tokens=max_tokens,
            temperature=0.2,
            top_p=0.9,
            repeat_penalty=1.1,
            stop=["Informe:", "\n\n\n"],
            stream=True,
        ):
            token = chunk["choices"][0]["text"]
            if token:
                yield token


# ─────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────


def _watch_gguf_download(
    repo: str,
    filename: str,
    total_mb: float,
    cache_root: Path,
    stop_event: threading.Event,
) -> None:
    """Hilo que reporta el progreso de descarga del GGUF cada 15 s."""
    safe_repo = repo.replace("/", "--")
    blob_dir = cache_root / f"models--{safe_repo}" / "blobs"

    while not stop_event.is_set():
        downloaded_mb = 0.0
        if blob_dir.exists():
            for f in blob_dir.iterdir():
                if f.is_file():
                    try:
                        downloaded_mb += f.stat().st_size / (1024 * 1024)
                    except OSError:
                        pass

        if downloaded_mb > 0:
            if total_mb:
                pct = min(100, downloaded_mb / total_mb * 100)
                logger.info(
                    "Descargando %s … %.0f MB / %.0f MB (%.1f%%)",
                    filename,
                    downloaded_mb,
                    total_mb,
                    pct,
                )
            else:
                logger.info(
                    "Descargando %s … %.0f MB descargados",
                    filename,
                    downloaded_mb,
                )

        stop_event.wait(15)


def _build_prompt(
    model_key: str, mode: str, text: str, system_prompt: str, user_prompt: str
) -> str:
    """Construye el prompt en el formato de chat de cada modelo.

    Usa ``str.replace`` en vez de ``str.format`` para evitar KeyError si el admin
    deja otras variables (ej. ``{language}``) sin rellenar en el prompt almacenado.
    """
    system = system_prompt
    user_msg = user_prompt.replace("{text}", text)

    if model_key in ("gemma3", "gemma4", "gemma4-2b"):
        return f"<start_of_turn>user\n{system}\n\n{user_msg}<end_of_turn>\n<start_of_turn>model\n"
    if model_key in ("phi4", "qwen"):
        return (
            f"<|im_start|>system\n{system}<|im_end|>\n"
            f"<|im_start|>user\n{user_msg}<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
    return f"{system}\n\n{user_msg}"


def _fallback_summary(text: str) -> str:
    word_count = len(text.split())
    return f"Informe clínico de {word_count} palabras procesado."


# ─────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────


def create_summarizer() -> "MedicalSummarizer | None":
    """Lee SUMMARIZER_MODEL y SUMMARIZER_MODE y devuelve un MedicalSummarizer o None."""
    model_key = os.environ.get("SUMMARIZER_MODEL", "none").strip().lower()
    if model_key == "none" or not model_key:
        logger.info("Resumidor desactivado (SUMMARIZER_MODEL=none).")
        return None
    if model_key not in MODELS:
        logger.warning(
            "SUMMARIZER_MODEL='%s' no reconocido. Opciones: %s. Resumidor desactivado.",
            model_key,
            list(MODELS.keys()),
        )
        return None
    mode = os.environ.get("SUMMARIZER_MODE", "summary").strip().lower()
    if mode not in MODES:
        logger.warning(
            "SUMMARIZER_MODE='%s' no reconocido. Opciones: %s. Usando 'summary'.",
            mode,
            list(MODES),
        )
        mode = "summary"
    system_prompt = os.environ.get("SUMMARIZER_SYSTEM_PROMPT", "").strip()
    user_prompt = os.environ.get("SUMMARIZER_USER_PROMPT", "").strip()

    # Defaults de arranque si no están configurados via env ni admin
    if not system_prompt:
        system_prompt = (
            "Eres un médico especialista en documentación clínica. "
            "Tu tarea es resumir informes clínicos de forma concisa y estructurada. "
            "Responde siempre en español. No añadas comentarios ni explicaciones fuera del resumen."
            if mode == "summary"
            else "Eres un médico especialista en documentación clínica. "
            "Tu tarea es reformular informes clínicos de forma clara y estructurada, "
            "conservando TODOS los detalles médicos: diagnósticos, fármacos, dosis, fechas y procedimientos. "
            "Responde siempre en español. No añadas ni omitas información médica."
        )
    if not user_prompt:
        user_prompt = (
            "Resume el siguiente informe clínico desde un punto de vista médico.\n"
            "Incluye: motivo de consulta, antecedentes relevantes, hallazgos exploratorios y analíticos, "
            "diagnóstico principal y procedimientos realizados. Máximo 120 palabras. Sin listas, en prosa continua.\n\n"
            "Informe:\n{text}\n\nResumen médico:"
            if mode == "summary"
            else "Reformula el siguiente informe clínico de forma clara y estructurada.\n"
            "Organiza la información en estas secciones (sin encabezados, en prosa continua): "
            "antecedentes y motivo de consulta, evolución clínica, hallazgos diagnósticos, "
            "tratamiento y procedimientos. Conserva TODOS los datos médicos exactos.\n\n"
            "Informe:\n{text}\n\nInforme reformulado:"
        )

    logger.info("Resumidor: modelo=%s modo=%s", model_key, mode)
    return MedicalSummarizer(model_key, mode, system_prompt, user_prompt)
