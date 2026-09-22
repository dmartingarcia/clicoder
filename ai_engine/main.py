"""
main.py: FastAPI service for the CIE-10 AI Engine.

Variables de entorno
--------------------
MODEL_DIR          Directorio con los artefactos del modelo.
                   Default: ./model
DEVICE             Dispositivo torch ('cpu', 'cuda', 'mps', …).
                   Default: cpu
SUMMARIZER_MODEL   Modelo LLM para resúmenes médicos: "gemma3" | "gemma4" | "gemma4-2b" | "phi4" | "qwen" | "none".
                   Default: none  (resumen estadístico básico)
SUMMARIZER_THREADS Hilos CPU para llama-cpp. Default: 4
SUMMARIZER_CTX     Contexto en tokens para llama-cpp. Default: 4096
"""

import asyncio
import glob
import json
import logging
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import numpy as np
import sentry_sdk
import structlog
import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from prometheus_client import Gauge, Histogram, Info
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

# ==================== STRUCTURED LOGGING ====================

_shared_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
]

structlog.configure(
    processors=[
        *_shared_processors,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

# Route stdlib logging (uvicorn startup messages, etc.) through structlog JSON
_stdlib_handler = logging.StreamHandler()
_stdlib_handler.setFormatter(
    structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=[
            *_shared_processors,
            structlog.stdlib.add_logger_name,
        ],
    )
)
logging.root.handlers = [_stdlib_handler]
logging.root.setLevel(logging.INFO)

logger = structlog.get_logger("cie10_engine")

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

# ==================== JOB STORE ====================

_JOB_TTL = 600  # segundos: los resultados se guardan 10 min tras completar
_jobs: dict[str, dict[str, Any]] = {}


async def _cleanup_expired_jobs() -> None:
    """Tarea en background que limpia jobs expirados cada 60 s."""
    while True:
        await asyncio.sleep(60)
        now = time.time()
        expired = [jid for jid, j in list(_jobs.items()) if j["expires_at"] < now]
        for jid in expired:
            _jobs.pop(jid, None)
        if expired:
            logger.info("Jobs expirados eliminados: %d", len(expired))


# ==================== LIFESPAN ====================


@asynccontextmanager
async def lifespan(app: FastAPI):
    global classifier, dict_classifier, summarizer, code_descriptions

    model_dir = os.environ.get("MODEL_DIR", "./model")
    device = os.environ.get("DEVICE", "cpu")

    if not os.path.isdir(model_dir):
        logger.warning(
            "MODEL_DIR '%s' no existe: el motor arranca sin modelo. "
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
            logger.warning("No se pudo cargar el modelo BERT: %s", exc, exc_info=True)
            sentry_sdk.capture_exception(exc)
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
                "baseline_dict.json no encontrado en '%s': engine=dict no disponible. "
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

    _cleanup_task = asyncio.create_task(_cleanup_expired_jobs())
    yield
    _cleanup_task.cancel()


# ==================== APP ====================

app = FastAPI(
    title="CIE-10 AI Engine",
    description="Clasificador RigoBERTa multi-label para codificación automática CIE-10.",
    version="2.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app)


# ==================== MIDDLEWARE ====================


_TEXT_ENDPOINTS = {"/predict", "/summarize/stream", "/jobs/predict", "/jobs/summarize"}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log detallado de requests: método, path, query params, texto y tiempo."""
    import json as _json

    start_time = time.perf_counter()
    query_params = dict(request.query_params) if request.query_params else None

    # Para endpoints de predicción/resumen, loguear el texto (primeros 300 chars)
    # request.body() cachea el resultado en request._body, así el endpoint puede leerlo
    text_preview = None
    if request.method == "POST" and request.url.path in _TEXT_ENDPOINTS:
        try:
            raw = await request.body()  # Starlette cachea en _body, no consume el stream
            data = _json.loads(raw)
            text = data.get("text", "")
            if text:
                text_preview = text[:300] + ("…" if len(text) > 300 else "")
        except Exception:
            pass

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        query_params=query_params,
        client_host=request.client.host if request.client else None,
        **({"text_preview": text_preview} if text_preview else {}),
    )

    return response


# ==================== SCHEMAS ====================


class AnalysisRequest(BaseModel):
    """Petición de análisis de un informe clínico.

    - ``text``: texto del informe (obligatorio, no vacío).
    - ``engine``:
        - ``"bert"`` : clasificador RigoBERTa multi-label (default).
        - ``"dict"`` : reglas por diccionario (determinista, sin GPU).
        - ``"both"`` : ambos motores en paralelo; los resultados se devuelven
          juntos con el campo ``engine`` identificando el origen de cada código.
    """

    text: str
    engine: Literal["bert", "dict", "both", "fused"] = "bert"
    include_triggers: bool = False
    """Calcular los términos explicativos en la misma petición.

    Desactivado por defecto porque la atribución cuesta del orden de cien veces más que
    la predicción: enmascara palabra por palabra y necesita una pasada del encoder por
    cada una. Con el valor por defecto, ``/predict`` devuelve los códigos en cuanto están
    y el cliente pide las explicaciones aparte con ``/explain``, mostrando un indicador de
    carga en su lugar. Poner esto a ``true`` reproduce el comportamiento anterior, en el
    que la respuesta completa esperaba a la atribución.
    """


class ExplainRequest(BaseModel):
    """Petición de explicabilidad para unos códigos ya predichos.

    Se separa de ``/predict`` para que el usuario reciba los códigos de inmediato y las
    palabras que los justifican lleguen después, cuando estén disponibles.
    """

    text: str
    codes: list[str]
    method: str | None = None
    """Estrategia de atribución. Si se omite, la configurada en el sistema."""
    top_k: int = 5


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


class SummarizerConfigRequest(BaseModel):
    model: str
    mode: str = "summary"
    system_prompt: str = ""
    user_prompt: str = ""


class SummarizeRequest(BaseModel):
    text: str
    system_prompt: str | None = None
    user_prompt: str | None = None


# ==================== ENDPOINTS ====================


@app.get("/", summary="Health check")
def health_check():
    return {
        "status": "online",
        "model": "rigoberta-cie10-flat",
        "model_loaded": classifier is not None,
        "dict_loaded": dict_classifier is not None,
        "summarizer_model": summarizer.model_name
        if summarizer and hasattr(summarizer, "model_name")
        else "none",
        "summarizer_loaded": summarizer.is_loaded
        if summarizer and hasattr(summarizer, "is_loaded")
        else False,
    }


class ModelLoadRequest(BaseModel):
    """Petición de cambio de modelo activo."""

    name: str
    """Nombre del modelo en el catálogo (models.json)."""


def _model_dir() -> str:
    return os.environ.get("MODEL_DIR", "./model")


def _catalogo_modelos() -> dict:
    """Catálogo de modelos publicados, o vacío si no se ha descargado."""
    ruta = Path(_model_dir()) / "models.json"
    if not ruta.exists():
        return {}
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("models.json ilegible: %s", exc)
        return {}


@app.get("/admin/models", summary="Modelos disponibles y cuál está cargado")
async def admin_list_models():
    """Lista el catálogo indicando cuáles están descargados y cuál sirve ahora mismo.

    Un modelo del catálogo puede no estar en disco: pesa algo más de 2 GB y se descarga por
    separado. Por eso se informa de ambas cosas, disponible y cargado, en lugar de solo una:
    sin esa distinción, intentar activar uno ausente fallaría sin explicación.
    """
    catalogo = _catalogo_modelos()
    activo = classifier.config.get("model_file") if classifier else None
    modelos = []
    for nombre, meta in catalogo.get("modelos", {}).items():
        fichero = Path(_model_dir()) / meta["checkpoint"]
        modelos.append(
            {
                "name": nombre,
                "checkpoint": meta["checkpoint"],
                "description": meta.get("descripcion", ""),
                "metrics": meta.get("comparables", {}),
                "downloaded": fichero.exists(),
                "loaded": meta["checkpoint"] == activo,
            }
        )
    return {
        "models": modelos,
        "loaded_checkpoint": activo,
        "note": catalogo.get("nota_medicion", ""),
    }


@app.post("/admin/models", summary="Cargar otro modelo en caliente")
async def admin_load_model(req: ModelLoadRequest):
    """Sustituye el modelo activo sin reiniciar el servicio.

    Se construye el clasificador nuevo entero y solo cuando ha cargado correctamente se pone
    en lugar del anterior, de modo que un fallo de carga deja el servicio sirviendo con el
    que ya tenía en vez de dejarlo sin ninguno.

    Cambia también el umbral y el umbral de fusión, que son propios de cada modelo: el de
    fusión vive en el espacio de la puntuación combinada, así que heredar el del modelo
    anterior degradaría los resultados de forma silenciosa.
    """
    global classifier

    catalogo = _catalogo_modelos()
    meta = catalogo.get("modelos", {}).get(req.name)
    if meta is None:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Modelo desconocido: {req.name}",
                "disponibles": sorted(catalogo.get("modelos", {})),
            },
        )

    destino = Path(_model_dir()) / meta["checkpoint"]
    if not destino.exists():
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"El modelo '{req.name}' no está descargado.",
                "solucion": f"make model-download NAME={req.name}",
            },
        )

    overrides = {
        "model_file": meta["checkpoint"],
        "thresholds_file": meta.get("thresholds", ""),
        "threshold": meta.get("umbral"),
        "fusion_threshold": meta.get("fusion_threshold"),
    }
    overrides = {k: v for k, v in overrides.items() if v not in (None, "")}

    _t0 = time.perf_counter()
    try:
        from classifier import CIE10Classifier

        nuevo = await asyncio.to_thread(
            CIE10Classifier,
            _model_dir(),
            os.environ.get("DEVICE", "cpu"),
            overrides,
        )
    except Exception as exc:
        logger.error("No se pudo cargar el modelo '%s': %s", req.name, exc)
        raise HTTPException(
            status_code=500,
            detail={"error": f"Fallo al cargar '{req.name}': {exc}"},
        ) from exc

    # Swap: hasta esta línea el modelo anterior seguía atendiendo peticiones.
    classifier = nuevo
    _t = time.perf_counter() - _t0
    logger.info("Modelo cambiado a '%s' en %.1f s", req.name, _t)
    return {
        "name": req.name,
        "checkpoint": meta["checkpoint"],
        "status": "loaded",
        "timing": {"load_ms": round(_t * 1000, 2)},
    }


@app.post("/admin/summarizer", summary="Hot-reload del summarizer LLM")
async def admin_summarizer(req: SummarizerConfigRequest):
    global summarizer
    from summarizer import MODELS, MedicalSummarizer

    valid_models = list(MODELS.keys()) + ["none"]
    valid_modes = ["summary", "paraphrase"]

    if req.model not in valid_models:
        raise HTTPException(status_code=422, detail=f"ERR_INVALID_MODEL:{req.model}")
    if req.mode not in valid_modes:
        raise HTTPException(status_code=422, detail=f"ERR_INVALID_MODE:{req.mode}")

    # Si el modelo y modo no cambian, solo actualizar prompts sin recargar
    model_unchanged = (
        summarizer is not None
        and summarizer.is_loaded
        and hasattr(summarizer, "_model_key")
        and summarizer._model_key == req.model
        and summarizer._mode == req.mode
    )

    if model_unchanged:
        try:
            summarizer.update_prompts(req.system_prompt, req.user_prompt)
            logger.info(
                "Prompts actualizados sin recargar modelo: model=%s mode=%s", req.model, req.mode
            )
            return {"model": req.model, "mode": req.mode, "status": "prompts_updated"}
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Modelo o modo cambiaron → cargar nuevo primero, luego descartar el viejo
    if req.model == "none":
        summarizer = None
        SUMMARIZER_LOADED.set(0)
        logger.info("Summarizer desactivado desde admin.")
        return {"model": "none", "mode": req.mode, "status": "disabled"}

    try:
        new_summarizer = MedicalSummarizer(req.model, req.mode, req.system_prompt, req.user_prompt)
        await asyncio.to_thread(new_summarizer.load)
        # Swap atómico: el viejo modelo sigue sirviendo hasta este punto
        summarizer = new_summarizer
        SUMMARIZER_LOADED.set(1)
        logger.info("Summarizer recargado: model=%s mode=%s", req.model, req.mode)
        return {"model": req.model, "mode": req.mode, "status": "loaded"}
    except Exception as exc:
        logger.error("Error cargando summarizer %s: %s", req.model, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
    if request.engine == "fused":
        return await _predict_fused(text, request.include_triggers)
    return await _predict_bert(text, request.include_triggers)


def _add_relative_confidence(codes: list[dict]) -> list[dict]:
    """Normalización min-max dentro del conjunto devuelto para comparación visual."""
    if len(codes) < 2:
        for c in codes:
            c["relative_confidence"] = 1.0
        return codes
    values = [c["confidence"] for c in codes]
    lo, hi = min(values), max(values)
    spread = hi - lo
    for c, v in zip(codes, values, strict=False):
        c["relative_confidence"] = round((v - lo) / spread, 4) if spread > 1e-6 else 1.0
    return codes


async def _predict_bert(text: str, incluir_triggers: bool = False):
    """Predicción BERT sin resumen. El resumen se genera por separado via /summarize/stream."""
    if classifier is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "Modelo BERT no cargado. Entrena con train.py y monta model/."},
        )

    _t0 = time.perf_counter()

    predictions = await asyncio.to_thread(classifier.predict, text, 10, code_descriptions or None)
    _t_classifier = time.perf_counter() - _t0

    code_triggers: dict[str, list] = {}
    if incluir_triggers:
        code_indices = [
            int(classifier.code_to_idx[p["code"]])
            for p in predictions
            if p["code"] in classifier.code_to_idx
        ]
        explanations = (
            await asyncio.to_thread(classifier.explain, text, code_indices) if code_indices else {}
        )
        code_triggers = {
            p["code"]: explanations.get(int(classifier.code_to_idx.get(p["code"], -1)), [])
            for p in predictions
        }

    _t_total = time.perf_counter() - _t0
    INFERENCE_LATENCY.labels(engine="bert").observe(_t_total)

    return {
        "cards": [
            {
                "type": "codes",
                "content": _add_relative_confidence(
                    [
                        {
                            "code": p["code"],
                            "description": p.get("description") or p.get("chapter_name", ""),
                            "reason": (
                                f"{p.get('chapter_name') or ('Capítulo ' + p.get('chapter', ''))}"
                                f": confianza {round(p['probability'] * 100, 1)}%"
                            ).strip(" :"),
                            "confidence": round(p["probability"], 4),
                            "triggers": code_triggers.get(p["code"], []),
                            "triggers_complete": incluir_triggers,
                            "engine": "bert",
                        }
                        for p in predictions
                    ]
                ),
            },
        ],
        "timing": {
            "classifier_ms": round(_t_classifier * 1000, 2),
            "summarizer_ms": 0,
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

    predictions = await asyncio.to_thread(dict_classifier.predict, text)
    _t_classifier = time.perf_counter() - _t0

    _t_total = time.perf_counter() - _t0
    INFERENCE_LATENCY.labels(engine="dict").observe(_t_total)

    return {
        "cards": [
            {
                "type": "codes",
                "content": _add_relative_confidence(
                    [
                        {
                            "code": p["code"],
                            "description": code_descriptions.get(p["code"], ""),
                            "reason": "Términos encontrados: " + ", ".join(p["matched_terms"]),
                            "confidence": p["confidence"],
                            "triggers": p["matched_terms"],
                            "engine": "dict",
                        }
                        for p in predictions
                    ]
                ),
            },
        ],
        "timing": {
            "classifier_ms": round(_t_classifier * 1000, 2),
            "summarizer_ms": 0,
            "total_ms": round(_t_total * 1000, 2),
        },
    }


def _dict_bonus_vector(hits: list[dict], code_to_idx: dict, beta: float):
    """Vector (num_codes,) con beta x confianza para los códigos del bloque detectado.

    El diccionario predice BLOQUES (los tres primeros caracteres del código), no códigos
    completos, así que la bonificación se reparte a todos los códigos del bloque por igual:
    aporta la evidencia léxica de qué bloque aplica y deja que el modelo decida el orden
    dentro de él. Medido sobre el conjunto de prueba, esto sube el MAP por documento de
    0,4342 a 0,5446 sin coste adicional de inferencia: el diccionario ya se ejecutaba.
    """
    bonus = np.zeros(len(code_to_idx), dtype=np.float32)
    por_bloque: dict[str, float] = {}
    for hit in hits:
        bloque = str(hit.get("code", "")).upper()[:3]
        conf = max(float(hit.get("confidence", 0.0)), 0.0)
        if bloque:
            por_bloque[bloque] = max(por_bloque.get(bloque, 0.0), conf)
    if not por_bloque:
        return bonus, 0
    for code, idx in code_to_idx.items():
        conf = por_bloque.get(str(code).upper()[:3])
        if conf:
            bonus[int(idx)] = beta * conf
    return bonus, len(por_bloque)


def _triggers_fusion(pred, explicaciones, terminos_dicc, code_to_idx, detallado=False):
    """Términos que explican un código en modo fusión, etiquetados por origen.

    Se devuelven hasta 5: primero las frases exactas del diccionario (evidencia léxica
    literal, la más convincente para un profesional) y después las palabras del modelo
    ordenadas por su importancia relativa. El peso del diccionario es la confianza del
    patrón; el del modelo, su importancia normalizada dentro del código. Son escalas
    distintas y se etiquetan como tales en lugar de mezclarse en un único orden.

    Las dos fuentes no cuestan lo mismo, y de ahí que la respuesta pueda llegar en dos
    tiempos. Los términos del diccionario ya están calculados cuando se llega aquí: el match
    por expresiones regulares se hizo para construir la bonificación, así que ofrecerlos es
    gratis y viajan en la respuesta de ``/predict``. Los del modelo exigen una pasada del
    encoder por palabra del informe y se piden aparte con ``/explain``. El cliente puede por
    tanto pintar la evidencia léxica de inmediato y completar con la del modelo cuando llegue,
    en lugar de esperar a todo o no mostrar nada.
    """
    idx = code_to_idx.get(pred["code"])
    bert = explicaciones.get(int(idx), []) if idx is not None else []
    dicc = terminos_dicc.get(str(pred["code"]).upper()[:3], []) if pred.get("dict_bonus") else []

    if not detallado:
        planos = list(dicc) + [t for t, _ in bert]
        vistos, salida = set(), []
        for t in planos:
            if t and t.lower() not in vistos:
                vistos.add(t.lower())
                salida.append(t)
        return salida[:5]

    detalle = [{"term": t, "source": "dict", "weight": None} for t in dicc[:3]]
    detalle += [{"term": t, "source": "bert", "weight": w} for t, w in bert[:5]]
    return detalle[:5]


async def _predict_fused(text: str, incluir_triggers: bool = False):
    """Fusión de puntuaciones entre BERT y el diccionario (no concatenación, como `both`).

    A diferencia de `both`, que devuelve las dos listas juntas y deja al usuario reconciliarlas,
    aquí las dos fuentes se combinan ANTES de ordenar: puntuación = logit + beta x confianza del
    diccionario. El umbral es propio y vive en el espacio de puntuación fusionada, porque el
    umbral de probabilidad heredado no sirve: la bonificación satura la probabilidad de todo
    código cuyo bloque haya hecho match.
    """
    if classifier is None or dict_classifier is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "El modo fused necesita el modelo BERT y el diccionario cargados. "
                "Revisa que existan classifier.pt y baseline_dict.json en model/."
            },
        )

    beta = float(classifier.config.get("fusion_beta", 6.0))
    score_thr = float(classifier.config.get("fusion_threshold", 2.9))

    _t0 = time.perf_counter()
    hits = await asyncio.to_thread(dict_classifier.predict, text)
    _t_dict = time.perf_counter() - _t0

    bonus, n_bloques = _dict_bonus_vector(hits, classifier.code_to_idx, beta)

    _t1 = time.perf_counter()
    predictions = await asyncio.to_thread(
        classifier.predict, text, 10, code_descriptions or None, None, bonus, score_thr
    )

    # Explicabilidad: las dos fuentes se reportan por separado y etiquetadas, no
    # mezcladas en un único ranking. Explican cosas distintas: el diccionario justifica
    # el BLOQUE con frases exactas, el modelo justifica el CÓDIGO dentro del bloque con
    # palabras del informe: y ordenarlas juntas exigiría una escala común entre la
    # confianza de un patrón regex y la caída de un logit, que no existe.
    code_indices = [
        int(classifier.code_to_idx[p["code"]])
        for p in predictions
        if p["code"] in classifier.code_to_idx
    ]
    explicaciones = (
        await asyncio.to_thread(classifier.explain, text, code_indices, 5, 16, True)
        if code_indices and incluir_triggers
        else {}
    )
    terminos_dicc = {str(h.get("code", "")).upper()[:3]: h.get("matched_terms", []) for h in hits}
    _t_bert = time.perf_counter() - _t1

    _t_total = time.perf_counter() - _t0
    INFERENCE_LATENCY.labels(engine="fused").observe(_t_total)

    return {
        "cards": [
            {
                "type": "codes",
                "content": _add_relative_confidence(
                    [
                        {
                            "code": p["code"],
                            "description": p.get("description") or p.get("chapter_name", ""),
                            "reason": (
                                f"{p.get('chapter_name') or ('Capítulo ' + p.get('chapter', ''))}"
                                f": confianza {round(p['probability'] * 100, 1)}%"
                                + (
                                    " · respaldado por el diccionario"
                                    if p.get("dict_bonus")
                                    else ""
                                )
                            ).strip(" :"),
                            "confidence": round(p["probability"], 4),
                            "triggers": _triggers_fusion(
                                p, explicaciones, terminos_dicc, classifier.code_to_idx
                            ),
                            "trigger_detail": _triggers_fusion(
                                p, explicaciones, terminos_dicc, classifier.code_to_idx, True
                            ),
                            "engine": "fused",
                            "dict_support": bool(p.get("dict_bonus")),
                            # Los términos del diccionario salen gratis: el match por regex ya
                            # se hizo para calcular la bonificación, así que viajan en esta misma
                            # respuesta. Los del modelo cuestan una pasada del encoder por palabra
                            # y se piden aparte con /explain. Este campo le dice al cliente si
                            # debe mostrar un indicador de carga y completar después.
                            "triggers_complete": incluir_triggers,
                            # Reparto exacto de la puntuación: cuánto puso cada fuente.
                            # No se convierte a porcentaje porque el logit puede ser
                            # negativo y un porcentaje sobre una suma con signos mezclados
                            # no significa nada.
                            "score_model": round(p["score"] - p.get("dict_bonus", 0.0), 4),
                            "score_dict": round(p.get("dict_bonus", 0.0), 4),
                        }
                        for p in predictions
                    ]
                ),
            },
        ],
        "timing": {
            "dict_classifier_ms": round(_t_dict * 1000, 2),
            "bert_classifier_ms": round(_t_bert * 1000, 2),
            "blocks_matched": n_bloques,
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

    bert_codes = bert_result["cards"][0]["content"]
    dict_codes = dict_result["cards"][0]["content"]
    all_codes = bert_codes + dict_codes

    return {
        "cards": [
            {"type": "codes", "content": all_codes},
        ],
        "timing": {
            "bert_classifier_ms": bert_result.get("timing", {}).get("classifier_ms", 0),
            "dict_classifier_ms": dict_result.get("timing", {}).get("classifier_ms", 0),
            "total_ms": round(_t_total * 1000, 2),
        },
    }


@app.post("/explain", summary="Términos que justifican unos códigos ya predichos")
async def explain_codes(request: ExplainRequest):
    """Calcula la atribución por separado de la predicción.

    La atribución cuesta del orden de cien veces más que predecir, porque mide el efecto
    real de quitar cada palabra del informe y eso exige una pasada del encoder por palabra.
    Atarla a ``/predict`` obligaba al usuario a esperar por algo que aún no está mirando:
    primero lee los códigos y solo después despliega uno para saber por qué se ha propuesto.
    Separarlas permite devolver los códigos de inmediato y resolver las explicaciones
    mientras el usuario ya está leyendo.
    """
    if classifier is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "Modelo BERT no cargado. Entrena con train.py y monta model/."},
        )
    texto = request.text.strip()
    if not texto:
        raise HTTPException(status_code=422, detail="El texto no puede estar vacío.")

    from classifier import METODOS_EXPLAIN

    # El diccionario explica sin tocar el encoder: los términos son las frases que hicieron
    # match por regex, así que se obtienen en centésimas de segundo en vez de en decenas.
    # En modo fusión estos mismos términos ya viajan en la respuesta de /predict sin coste;
    # esta vía existe para el motor neuronal, que no ejecuta el diccionario.
    if request.method == "diccionario":
        if dict_classifier is None:
            raise HTTPException(
                status_code=503,
                detail={"error": "Diccionario no disponible: falta baseline_dict.json en model/."},
            )
        _t0 = time.perf_counter()
        hits = await asyncio.to_thread(dict_classifier.predict, texto)
        por_bloque = {str(h.get("code", "")).upper()[:3]: h for h in hits}
        _t = time.perf_counter() - _t0
        INFERENCE_LATENCY.labels(engine="explain:diccionario").observe(_t)
        return {
            "method": "diccionario",
            "triggers": {
                code: [
                    {"term": termino, "weight": None}
                    for termino in por_bloque.get(code.upper()[:3], {}).get("matched_terms", [])
                ][: request.top_k]
                for code in request.codes
            },
            "unknown_codes": [],
            "timing": {"explain_ms": round(_t * 1000, 2)},
        }

    if request.method is not None and request.method not in METODOS_EXPLAIN:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Método de atribución desconocido: {request.method}",
                "disponibles": sorted([*METODOS_EXPLAIN, "diccionario"]),
            },
        )

    indices, conocidos = [], []
    for code in request.codes:
        idx = classifier.code_to_idx.get(code)
        if idx is not None:
            indices.append(int(idx))
            conocidos.append(code)

    _t0 = time.perf_counter()
    explicaciones = (
        await asyncio.to_thread(
            classifier.explain, texto, indices, request.top_k, 16, True, request.method
        )
        if indices
        else {}
    )
    _t = time.perf_counter() - _t0
    metodo = request.method or classifier.config.get("explain_method", "exhaustivo")
    INFERENCE_LATENCY.labels(engine=f"explain:{metodo}").observe(_t)

    return {
        # El método viaja en la respuesta: sin él, ante un término extraño no hay forma de
        # saber si lo produjo la versión fiel o una de las rápidas.
        "method": metodo,
        "triggers": {
            code: [
                {"term": termino, "weight": peso}
                for termino, peso in explicaciones.get(int(classifier.code_to_idx[code]), [])
            ]
            for code in conocidos
        },
        "unknown_codes": [c for c in request.codes if c not in conocidos],
        "timing": {"explain_ms": round(_t * 1000, 2)},
    }


@app.post("/summarize/stream", summary="Resumen médico en streaming (NDJSON)")
async def summarize_stream(request: SummarizeRequest):
    """Genera el resumen/paráfrasis del texto token a token.

    Devuelve NDJSON: una línea JSON por token + línea final ``{"done": true}``.
    Si el summarizer no está cargado devuelve un único chunk con el fallback estadístico.
    """
    import json as _json
    import threading

    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="El texto no puede estar vacío.")

    async def _stream():
        if summarizer is None:
            word_count = len(text.split())
            yield (
                _json.dumps({"token": f"Informe clínico de {word_count} palabras procesado."})
                + "\n"
            )
            yield _json.dumps({"done": True}) + "\n"
            return

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def _run():
            try:
                for token in summarizer.summarize_stream(
                    text,
                    system_prompt=request.system_prompt,
                    user_prompt=request.user_prompt,
                ):
                    loop.call_soon_threadsafe(queue.put_nowait, {"token": token})
            except Exception as exc:
                logger.warning("Error en streaming del summarizer: %s", exc)
                loop.call_soon_threadsafe(queue.put_nowait, {"error": str(exc)})
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, {"done": True})

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        while True:
            item = await queue.get()
            yield _json.dumps(item) + "\n"
            if "done" in item or "error" in item:
                break

        thread.join(timeout=5)

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


# ==================== ASYNC JOB ENDPOINTS ====================


def _new_job() -> tuple[str, dict[str, Any]]:
    """Crea un job en estado pending y lo registra en _jobs."""
    job_id = uuid.uuid4().hex
    job: dict[str, Any] = {
        "status": "pending",
        "result": None,
        "error": None,
        "expires_at": time.time() + _JOB_TTL,
    }
    _jobs[job_id] = job
    return job_id, job


@app.post("/jobs/predict", summary="Predicción asíncrona: devuelve job_id inmediatamente")
async def submit_predict_job(request: AnalysisRequest):
    """Encola la predicción y devuelve un ``job_id``.

    Elixir puede hacer GET /jobs/{job_id} para recuperar el resultado
    cuando esté listo, aunque la conexión original se haya cortado.
    Los resultados se guardan durante 10 minutos tras completar.
    """
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="El texto no puede estar vacío.")

    job_id, job = _new_job()

    async def _run():
        try:
            if request.engine == "dict":
                job["result"] = await _predict_dict(text)
            elif request.engine == "both":
                job["result"] = await _predict_both(text)
            else:
                job["result"] = await _predict_bert(text)
            job["status"] = "done"
        except HTTPException as exc:
            job["error"] = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            job["status"] = "error"
        except Exception as exc:
            job["error"] = str(exc)
            job["status"] = "error"
        finally:
            job["expires_at"] = time.time() + _JOB_TTL

    asyncio.create_task(_run())
    return {"job_id": job_id, "status": "pending"}


@app.post("/jobs/summarize", summary="Resumen asíncrono: devuelve job_id inmediatamente")
async def submit_summarize_job(request: SummarizeRequest):
    """Encola el resumen y devuelve un ``job_id``.

    El resultado es ``{"text": "..."}`` cuando status == "done".
    Los resultados se guardan durante 10 minutos tras completar.
    """
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="El texto no puede estar vacío.")

    job_id, job = _new_job()

    async def _run():
        try:
            if summarizer is None:
                word_count = len(text.split())
                job["result"] = {"text": f"Informe clínico de {word_count} palabras procesado."}
            else:
                summary_text = await asyncio.to_thread(summarizer.summarize, text)
                job["result"] = {"text": summary_text}
            job["status"] = "done"
        except Exception as exc:
            job["error"] = str(exc)
            job["status"] = "error"
        finally:
            job["expires_at"] = time.time() + _JOB_TTL

    asyncio.create_task(_run())
    return {"job_id": job_id, "status": "pending"}


@app.get("/jobs/{job_id}", summary="Consultar estado y resultado de un job")
async def get_job(job_id: str):
    """Devuelve el estado del job.

    - ``status: "pending"``, en proceso, vuelve a consultar en unos segundos.
    - ``status: "done"``   , result contiene la respuesta completa.
    - ``status: "error"``  , error contiene el mensaje de error.

    Devuelve 404 si el job no existe o ha expirado (>10 min desde que completó).
    """
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job no encontrado o expirado.")
    return {
        "job_id": job_id,
        "status": job["status"],
        "result": job["result"],
        "error": job["error"],
    }
