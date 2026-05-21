"""
summarizer.py — Resumen médico de informes clínicos via LLM local (GGUF/llama-cpp).

Variables de entorno
--------------------
SUMMARIZER_MODEL   Modelo a usar: "gemma3" | "phi4" | "qwen" | "none" (default: "none").
                   Con "none" se devuelve el resumen estadístico básico.
SUMMARIZER_THREADS Número de hilos CPU para llama-cpp (default: 4).
SUMMARIZER_CTX     Tamaño de contexto en tokens (default: 4096).
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
        "repo": "bartowski/gemma-3-4b-it-GGUF",
        "filename": "gemma-3-4b-it-Q4_K_M.gguf",
        "display": "Gemma 3 4B IT",
        "size_gb": 2.5,
    },
    "phi4": {
        "repo": "bartowski/Phi-4-mini-instruct-GGUF",
        "filename": "Phi-4-mini-instruct-Q4_K_M.gguf",
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
# Prompt médico estructurado
# ─────────────────────────────────────────────

SYSTEM_PROMPT = (
    "Eres un médico especialista en documentación clínica. "
    "Tu tarea es resumir informes clínicos de forma concisa y estructurada. "
    "Responde siempre en español. No añadas comentarios ni explicaciones fuera del resumen."
)

USER_PROMPT_TEMPLATE = """Resume el siguiente informe clínico desde un punto de vista médico.
Incluye en el resumen: motivo de consulta, antecedentes relevantes, hallazgos exploratorios y analíticos, \
diagnóstico principal y procedimientos realizados. Máximo 120 palabras. Sin listas, en prosa continua.

Informe:
{text}

Resumen médico:"""


class MedicalSummarizer:
    """Genera resúmenes médicos usando un LLM local en formato GGUF."""

    def __init__(self, model_key: str):
        if model_key not in MODELS:
            raise ValueError(f"Modelo desconocido: '{model_key}'. Opciones: {list(MODELS.keys())}")
        self._model_key = model_key
        self._cfg = MODELS[model_key]
        self._llm = None
        self._n_threads = int(os.environ.get("SUMMARIZER_THREADS", "4"))
        self._n_ctx = int(os.environ.get("SUMMARIZER_CTX", "4096"))

    # ── Propiedades públicas ───────────────────────────────────────────────

    @property
    def model_name(self) -> str:
        return self._cfg["display"]

    @property
    def is_loaded(self) -> bool:
        return self._llm is not None

    # ── Carga / descarga ───────────────────────────────────────────────────

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

    def summarize(self, text: str, max_tokens: int = 250) -> str:
        """Genera un resumen médico del texto. Llama a load() si no está cargado."""
        if not self.is_loaded:
            self.load()

        # Truncar input para no exceder el contexto
        words = text.split()
        if len(words) > 600:
            text = " ".join(words[:600])

        prompt = _build_prompt(self._model_key, text)

        output = self._llm(
            prompt,
            max_tokens=max_tokens,
            temperature=0.2,
            top_p=0.9,
            repeat_penalty=1.1,
            stop=["Informe:", "\n\n\n"],
        )
        summary = output["choices"][0]["text"].strip()

        # Limpiar artefactos frecuentes de algunos modelos
        for prefix in ("Resumen médico:", "Resumen:", "**Resumen médico:**"):
            if summary.startswith(prefix):
                summary = summary[len(prefix) :].strip()

        return summary or _fallback_summary(text)


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


def _build_prompt(model_key: str, text: str) -> str:
    """Construye el prompt en el formato de chat de cada modelo."""
    user_msg = USER_PROMPT_TEMPLATE.format(text=text)

    if model_key == "gemma3":
        # Gemma 3 usa <start_of_turn> / <end_of_turn>
        return (
            f"<start_of_turn>user\n{SYSTEM_PROMPT}\n\n{user_msg}<end_of_turn>\n"
            "<start_of_turn>model\n"
        )
    if model_key == "phi4":
        # Phi-4 usa ChatML
        return (
            f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
            f"<|im_start|>user\n{user_msg}<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
    if model_key == "qwen":
        # Qwen 2.5 usa ChatML igual que Phi
        return (
            f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
            f"<|im_start|>user\n{user_msg}<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
    # Fallback genérico
    return f"{SYSTEM_PROMPT}\n\n{user_msg}"


def _fallback_summary(text: str) -> str:
    word_count = len(text.split())
    return f"Informe clínico de {word_count} palabras procesado."


# ─────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────


def create_summarizer() -> "MedicalSummarizer | None":
    """Lee SUMMARIZER_MODEL y devuelve un MedicalSummarizer o None si está desactivado."""
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
    return MedicalSummarizer(model_key)
