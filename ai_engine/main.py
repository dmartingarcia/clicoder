"""
main.py — FastAPI service for the CIE-10 AI Engine.

Variables de entorno
--------------------
MODEL_DIR          Directorio con los artefactos del modelo.
                   Default: ./model
DEVICE             Dispositivo torch ('cpu', 'cuda', 'mps', …).
                   Default: cpu
SUMMARIZER_MODEL   Modelo LLM para resúmenes médicos: "gemma3" | "phi4" | "qwen" | "none".
                   Default: none  (resumen estadístico básico)
SUMMARIZER_THREADS Hilos CPU para llama-cpp. Default: 4
SUMMARIZER_CTX     Contexto en tokens para llama-cpp. Default: 4096
"""

import asyncio
import glob
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import sentry_sdk
import structlog
import torch
from fastapi import FastAPI, HTTPException, Request
from prometheus_client import Gauge, Histogram, Info
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

# ==================== STRUCTURED LOGGING ====================

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

logger = structlog.get_logger("cie10_engine")
logging.basicConfig(level=logging.INFO, format="%(message)s")

# ==================== MÉTRICAS PROMETHEUS ====================

INFERENCE_LATENCY = Histogram(
    "cie10_inference_duration_seconds",
    "Latencia de inferencia del clasificador por motor",
    ["engine"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)
MODEL_LOADED = Gauge("cie10_model_loaded", "1 si el modelo BERT está cargado")
MODEL_INFO = Info("cie10_model", "Metadatos del modelo BERT cargado")
DICT_LOADED = Gauge("cie10_dict_loaded", "1 si el clasificador de diccionario está cargado")
SUMMARIZER_LOADED = Gauge("cie10_summarizer_loaded", "1 si el summarizer LLM está cargado")

# ==================== SENTRY ====================

if _sentry_dsn := os.environ.get("SENTRY_DSN_AI"):
    sentry_sdk.init(
        dsn=_sentry_dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
    )


def _watch_download(model_name: str, stop_event: threading.Event) -> None:
    """Hilo que reporta progreso de descarga del modelo cada 15 s."""
    try:
        from huggingface_hub import constants as hf_c

        cache_root = Path(hf_c.HF_HUB_CACHE)
    except Exception:
        cache_root = Path.home() / ".cache" / "huggingface" / "hub"

    safe_name = model_name.replace("/", "--")
    model_cache = cache_root / f"models--{safe_name}"

    # Intentamos obtener el tamaño total del modelo vía API (best-effort)
    total_mb: float = 0.0
    try:
        from huggingface_hub import model_info as hf_model_info

        info = hf_model_info(model_name)
        if getattr(info, "safetensors", None) and info.safetensors.total:
            total_mb = info.safetensors.total / (1024 * 1024)
    except Exception:
        pass

    while not stop_event.is_set():
        if model_cache.exists():
            size_mb = sum(f.stat().st_size for f in model_cache.rglob("*") if f.is_file()) / (
                1024 * 1024
            )
            if total_mb:
                pct = min(100, size_mb / total_mb * 100)
                logger.info(
                    "Descargando %s … %.0f MB / %.0f MB (%.1f%%)",
                    model_name,
                    size_mb,
                    total_mb,
                    pct,
                )
            else:
                logger.info("Descargando %s … %.0f MB descargados", model_name, size_mb)
        stop_event.wait(15)


# Globals poblados en startup
classifier = None  # CIE10Classifier (BERT)
dict_classifier = None  # DictClassifier (diccionario)
summarizer = None  # MedicalSummarizer (LLM local, opcional)
code_descriptions: dict[str, str] = {}


# ==================== LIFESPAN ====================


@asynccontextmanager
async def lifespan(app: FastAPI):
    global classifier, dict_classifier, summarizer, code_descriptions

    model_dir = os.environ.get("MODEL_DIR", "./model")
    device = os.environ.get("DEVICE", "cpu")

    if not os.path.isdir(model_dir):
        logger.warning(
            "MODEL_DIR '%s' no existe — el motor arranca sin modelo. "
            "/predict devolverá 503 hasta que se entrene y monte el modelo.",
            model_dir,
        )
    else:
        # ── BERT classifier ──────────────────────────────────────────────────
        try:
            import json as _json

            from classifier import CIE10Classifier, load_code_descriptions

            # Detectar model_name para el monitor de descarga
            _cfg_path = Path(model_dir) / "config.json"
            _model_name = "IIC/RigoBERTa-Clinical"
            if _cfg_path.exists():
                with open(_cfg_path) as _f:
                    _model_name = _json.load(_f).get("model_name", _model_name)

            _stop = threading.Event()
            _watcher = threading.Thread(
                target=_watch_download, args=(_model_name, _stop), daemon=True
            )
            _watcher.start()
            logger.info("Cargando modelo BERT desde '%s' en device='%s' …", model_dir, device)

            classifier = CIE10Classifier(model_dir=model_dir, device=device)
            code_descriptions = load_code_descriptions(model_dir)
            MODEL_LOADED.set(1)

            _stop.set()
            _pt_files = sorted(glob.glob(os.path.join(model_dir, "classifier_*.pt")))
            _checkpoint = os.path.basename(_pt_files[-1]) if _pt_files else "classifier.pt"
            MODEL_INFO.info({"model_name": _model_name, "checkpoint": _checkpoint})

            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                gpu_mem = torch.cuda.get_device_properties(0).total_memory // (1024**2)
                _device_info = f"GPU: {gpu_name} ({gpu_mem} MB VRAM)"
            else:
                _device_info = "CPU"
            logger.info(
                "Modelo cargado: %s | checkpoint: %s | %d códigos CIE-10 | %s",
                _model_name,
                _checkpoint,
                len(code_descriptions),
                _device_info,
            )
        except Exception as exc:
            logger.warning("No se pudo cargar el modelo BERT: %s", exc)
            classifier = None

        # ── Diccionario classifier ────────────────────────────────────────────
        dict_path = os.path.join(model_dir, "baseline_dict.json")
        if os.path.isfile(dict_path):
            try:
                from baseline_dict import DictClassifier

                logger.info("Cargando clasificador de diccionario desde '%s' …", dict_path)
                dict_classifier = DictClassifier(dict_path)
                DICT_LOADED.set(1)
                n_blocks = len(dict_classifier._patterns)
                n_patterns = sum(len(v) for v in dict_classifier._patterns.values())
                logger.info(
                    "Diccionario cargado: %d bloques, %d patrones.",
                    n_blocks,
                    n_patterns,
                )
            except Exception as exc:
                logger.warning("No se pudo cargar el clasificador de diccionario: %s", exc)
                dict_classifier = None
        else:
            logger.info(
                "baseline_dict.json no encontrado en '%s' — engine=dict no disponible. "
                "Genera el fichero con: python baseline_dict.py --save_dict %s",
                model_dir,
                dict_path,
            )

    # ── Summarizer (LLM local, opcional) ─────────────────────────────────
    try:
        from summarizer import create_summarizer

        summarizer = create_summarizer()
        if summarizer is not None:
            # Carga en hilo para no bloquear el arranque
            await asyncio.to_thread(summarizer.load)
            SUMMARIZER_LOADED.set(1)
    except Exception as exc:
        logger.warning("No se pudo inicializar el resumidor: %s", exc)
        summarizer = None
        SUMMARIZER_LOADED.set(0)

    yield


# ==================== APP ====================

app = FastAPI(
    title="CIE-10 AI Engine",
    description="Clasificador RigoBERTa multi-label para codificación automática CIE-10.",
    version="2.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app)


# ==================== MIDDLEWARE ====================


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log detallado de requests: método, path, query params, tiempo."""
    start_time = time.perf_counter()

    # Capturar parámetros de query
    query_params = dict(request.query_params) if request.query_params else None

    response = await call_next(request)

    # Tiempo de procesamiento
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # Log estructurado
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        query_params=query_params,
        client_host=request.client.host if request.client else None,
    )

    return response


# ==================== SCHEMAS ====================


class AnalysisRequest(BaseModel):
    """Petición de análisis de un informe clínico.

    - ``text``: texto del informe (obligatorio, no vacío).
    - ``engine``:
        - ``"bert"``  — clasificador RigoBERTa multi-label (default).
        - ``"dict"``  — reglas por diccionario (determinista, sin GPU).
        - ``"both"``  — ambos motores en paralelo; los resultados se devuelven
          juntos con el campo ``engine`` identificando el origen de cada código.
    """

    text: str
    engine: Literal["bert", "dict", "both"] = "bert"


class TimingInfo(BaseModel):
    """Información de timing de la inferencia en milisegundos.

    Nota: classifier_ms y summarizer_ms se ejecutan en paralelo,
    por lo que total_ms será menor que su suma.
    """

    classifier_ms: float
    summarizer_ms: float
    total_ms: float


class CodePrediction(BaseModel):
    """Código CIE-10 predicho con metadatos."""

    code: str
    description: str
    reason: str
    confidence: float
    engine: str


class Card(BaseModel):
    """Tarjeta de resultado (resumen o códigos)."""

    type: str
    content: str | list[CodePrediction]


class PredictResponse(BaseModel):
    """Respuesta del endpoint /predict con timing desglosado."""

    cards: list[Card]
    timing: TimingInfo


class TokenCountRequest(BaseModel):
    text: str


# ==================== ENDPOINTS ====================


@app.get("/", summary="Health check")
def health_check():
    return {
        "status": "online",
        "model": "rigoberta-cie10-flat",
        "model_loaded": classifier is not None,
        "dict_loaded": dict_classifier is not None,
        "summarizer_model": summarizer.model_name if summarizer else "none",
        "summarizer_loaded": summarizer.is_loaded if summarizer else False,
    }


@app.post("/count-tokens", summary="Contar tokens del tokenizador")
async def count_tokens(request: TokenCountRequest):
    if classifier is None:
        raise HTTPException(status_code=503, detail="Modelo no cargado.")
    enc = await asyncio.to_thread(
        classifier.tokenizer,
        request.text,
        add_special_tokens=True,
        truncation=False,
    )
    return {"token_count": len(enc["input_ids"])}


@app.post(
    "/predict",
    summary="Predecir códigos CIE-10",
    description=(
        "Analiza el texto de un informe clínico y devuelve códigos CIE-10 candidatos. "
        "El parámetro ``engine`` selecciona el motor de predicción: "
        "``bert`` (default), ``dict`` (diccionario determinista) o ``both`` (ambos en paralelo)."
    ),
)
async def predict_codes(request: AnalysisRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="El texto no puede estar vacío.")

    if request.engine == "dict":
        return await _predict_dict(text)
    if request.engine == "both":
        return await _predict_both(text)
    return await _predict_bert(text)


async def _predict_bert(text: str):
    if classifier is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "Modelo BERT no cargado. Entrena con train.py y monta model/."},
        )

    _t0 = time.perf_counter()

    # Ejecutar en paralelo y medir tiempos individuales
    async def _timed_classifier():
        _t_start = time.perf_counter()
        result = await asyncio.to_thread(classifier.predict, text, 10, code_descriptions or None)
        return result, time.perf_counter() - _t_start

    async def _timed_summary():
        _t_start = time.perf_counter()
        result = await _generate_summary(text)
        return result, time.perf_counter() - _t_start

    (predictions, _t_classifier), (summary_text, _t_summary) = await asyncio.gather(
        _timed_classifier(), _timed_summary()
    )

    _t_total = time.perf_counter() - _t0
    INFERENCE_LATENCY.labels(engine="bert").observe(_t_total)

    return {
        "cards": [
            {"type": "summary", "content": summary_text},
            {
                "type": "codes",
                "content": [
                    {
                        "code": p["code"],
                        "description": p.get("description") or p.get("chapter_name", ""),
                        "reason": (
                            f"{p.get('chapter_name') or ('Capítulo ' + p.get('chapter', ''))} "
                            f"— confianza {round(p['probability'] * 100, 1)}%"
                        ).strip(" —"),
                        "confidence": round(p["probability"], 4),
                        "engine": "bert",
                    }
                    for p in predictions
                ],
            },
        ],
        "timing": {
            "classifier_ms": round(_t_classifier * 1000, 2),
            "summarizer_ms": round(_t_summary * 1000, 2),
            "total_ms": round(_t_total * 1000, 2),
        },
    }


async def _predict_dict(text: str):  # noqa: E302
    if dict_classifier is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Clasificador de diccionario no disponible. "
                "Genera baseline_dict.json con: "
                "python baseline_dict.py --sources clinical corpus combined "
                "--corpus_selective --only_combined --save_dict model/baseline_dict.json"
            },
        )

    _t0 = time.perf_counter()

    # Ejecutar en paralelo y medir tiempos individuales
    async def _timed_classifier():
        _t_start = time.perf_counter()
        result = await asyncio.to_thread(dict_classifier.predict, text)
        return result, time.perf_counter() - _t_start

    async def _timed_summary():
        _t_start = time.perf_counter()
        result = await _generate_summary(text)
        return result, time.perf_counter() - _t_start

    (predictions, _t_classifier), (summary_text, _t_summary) = await asyncio.gather(
        _timed_classifier(), _timed_summary()
    )

    _t_total = time.perf_counter() - _t0
    INFERENCE_LATENCY.labels(engine="dict").observe(_t_total)

    return {
        "cards": [
            {"type": "summary", "content": summary_text},
            {
                "type": "codes",
                "content": [
                    {
                        "code": p["code"],
                        "description": code_descriptions.get(p["code"], ""),
                        "reason": "Términos encontrados: " + ", ".join(p["matched_terms"]),
                        "confidence": p["confidence"],
                        "matched_terms": p["matched_terms"],
                        "engine": "dict",
                    }
                    for p in predictions
                ],
            },
        ],
        "timing": {
            "classifier_ms": round(_t_classifier * 1000, 2),
            "summarizer_ms": round(_t_summary * 1000, 2),
            "total_ms": round(_t_total * 1000, 2),
        },
    }


async def _predict_both(text: str):
    """Llama a BERT y al diccionario en paralelo y devuelve sus predicciones juntas.

    Cada código conserva su campo ``engine`` ("bert" o "dict") para que el
    frontend pueda distinguir el origen. No se deduplicaan: un código puede
    aparecer dos veces si ambos motores lo detectan.
    """
    _t0 = time.perf_counter()
    bert_result, dict_result = await asyncio.gather(
        _predict_bert(text),
        _predict_dict(text),
    )
    _t_total = time.perf_counter() - _t0

    bert_codes = bert_result["cards"][1]["content"]
    dict_codes = dict_result["cards"][1]["content"]
    all_codes = bert_codes + dict_codes

    # El resumen ya viene generado en bert_result (se calculó en paralelo)
    summary_card = bert_result["cards"][0]

    return {
        "cards": [
            summary_card,
            {"type": "codes", "content": all_codes},
        ],
        "timing": {
            "bert_classifier_ms": bert_result.get("timing", {}).get("classifier_ms", 0),
            "bert_summarizer_ms": bert_result.get("timing", {}).get("summarizer_ms", 0),
            "dict_classifier_ms": dict_result.get("timing", {}).get("classifier_ms", 0),
            "dict_summarizer_ms": dict_result.get("timing", {}).get("summarizer_ms", 0),
            "total_ms": round(_t_total * 1000, 2),
        },
    }


# ─────────────────────────────────────────────
# Helper: generación de resumen
# ─────────────────────────────────────────────


async def _generate_summary(text: str) -> str:
    """Genera un resumen médico real si el summarizer está activo, o uno básico si no."""
    if summarizer is not None:
        try:
            return await asyncio.to_thread(summarizer.summarize, text)
        except Exception as exc:
            logger.warning("Error al generar resumen con LLM: %s — usando resumen básico.", exc)

    # Fallback: resumen estadístico básico
    word_count = len(text.split())
    return f"Informe clínico de {word_count} palabras procesado."
