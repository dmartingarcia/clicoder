"""
main.py — FastAPI service for the CIE-10 AI Engine.

Variables de entorno
--------------------
MODEL_DIR   Directorio con los artefactos del modelo.
            Default: ./model
DEVICE      Dispositivo torch ('cpu', 'cuda', 'mps', …).
            Default: cpu
"""

import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("cie10_engine")
logging.basicConfig(level=logging.INFO)


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
            size_mb = sum(
                f.stat().st_size for f in model_cache.rglob("*") if f.is_file()
            ) / (1024 * 1024)
            if total_mb:
                pct = min(100, size_mb / total_mb * 100)
                logger.info(
                    "Descargando %s … %.0f MB / %.0f MB (%.1f%%)",
                    model_name, size_mb, total_mb, pct,
                )
            else:
                logger.info("Descargando %s … %.0f MB descargados", model_name, size_mb)
        stop_event.wait(15)

# Globals poblados en startup
classifier        = None   # CIE10Classifier (BERT)
dict_classifier   = None   # DictClassifier (diccionario)
code_descriptions: Dict[str, str] = {}


# ==================== LIFESPAN ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    global classifier, dict_classifier, code_descriptions

    model_dir = os.environ.get("MODEL_DIR", "./model")
    device    = os.environ.get("DEVICE", "cpu")

    if not os.path.isdir(model_dir):
        logger.warning(
            "MODEL_DIR '%s' no existe — el motor arranca sin modelo. "
            "/predict devolverá 503 hasta que se entrene y monte el modelo.",
            model_dir,
        )
    else:
        # ── BERT classifier ──────────────────────────────────────────────────
        try:
            from classifier import CIE10Classifier, load_code_descriptions
            import json as _json

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

            classifier        = CIE10Classifier(model_dir=model_dir, device=device)
            code_descriptions = load_code_descriptions(model_dir)

            _stop.set()
            import torch as _torch
            if _torch.cuda.is_available():
                gpu_name = _torch.cuda.get_device_name(0)
                gpu_mem  = _torch.cuda.get_device_properties(0).total_memory // (1024 ** 2)
                logger.info("Ejecutando en GPU: %s (%d MB VRAM)", gpu_name, gpu_mem)
            else:
                logger.info("Ejecutando en CPU (sin GPU disponible)")
            logger.info("Modelo BERT cargado. %d descripciones disponibles.", len(code_descriptions))
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
                n_blocks = len(dict_classifier._patterns)
                n_patterns = sum(len(v) for v in dict_classifier._patterns.values())
                logger.info("Diccionario cargado: %d bloques, %d patrones.", n_blocks, n_patterns)
            except Exception as exc:
                logger.warning("No se pudo cargar el clasificador de diccionario: %s", exc)
                dict_classifier = None
        else:
            logger.info(
                "baseline_dict.json no encontrado en '%s' — engine=dict no disponible. "
                "Genera el fichero con: python baseline_dict.py --save_dict %s",
                model_dir, dict_path,
            )

    yield


# ==================== APP ====================

app = FastAPI(
    title="CIE-10 AI Engine",
    description="Clasificador RigoBERTa multi-label para codificación automática CIE-10.",
    version="2.0.0",
    lifespan=lifespan,
)


# ==================== SCHEMAS ====================

class AnalysisRequest(BaseModel):
    text: str
    engine: Literal["bert", "dict"] = "bert"


# ==================== ENDPOINTS ====================

@app.get("/", summary="Health check")
def health_check():
    return {
        "status":       "online",
        "model":        "rigoberta-cie10-flat",
        "model_loaded": classifier is not None,
        "dict_loaded":  dict_classifier is not None,
    }


@app.post("/predict", summary="Predecir códigos CIE-10")
async def predict_codes(request: AnalysisRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="El texto no puede estar vacío.")

    if request.engine == "dict":
        return await _predict_dict(text)
    return await _predict_bert(text)


async def _predict_bert(text: str):
    if classifier is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "Modelo BERT no cargado. Entrena con train.py y monta model/."},
        )

    predictions = await asyncio.to_thread(
        classifier.predict, text, 10, code_descriptions or None,
    )

    word_count = len(text.split())
    n_codes    = len(predictions)
    codes_str  = ", ".join(p["code"] for p in predictions) if predictions else "ninguno"

    return {"cards": [
        {
            "type": "summary",
            "content": (
                f"Informe clínico analizado ({word_count} palabras). "
                f"{n_codes} código(s) CIE-10 identificado(s): {codes_str}."
            ),
        },
        {
            "type": "codes",
            "content": [
                {
                    "code":        p["code"],
                    "description": p.get("description") or p.get("chapter_name", ""),
                    "reason":      (
                        f"{p.get('chapter_name') or ('Capítulo ' + p.get('chapter',''))} "
                        f"— confianza {round(p['probability'] * 100, 1)}%"
                    ).strip(" —"),
                    "confidence":  round(p["probability"], 4),
                    "engine":      "bert",
                }
                for p in predictions
            ],
        },
        {
            "type": "recommendations",
            "content": (
                "Revisar y confirmar los códigos asignados con el equipo médico "
                "antes de registrar el alta."
            ),
        },
    ]}


async def _predict_dict(text: str):
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

    predictions = await asyncio.to_thread(dict_classifier.predict, text)

    word_count = len(text.split())
    n_codes    = len(predictions)
    codes_str  = ", ".join(p["code"] for p in predictions) if predictions else "ninguno"

    return {"cards": [
        {
            "type": "summary",
            "content": (
                f"Informe clínico analizado ({word_count} palabras). "
                f"{n_codes} código(s) CIE-10 identificado(s) por diccionario: {codes_str}."
            ),
        },
        {
            "type": "codes",
            "content": [
                {
                    "code":          p["code"],
                    "description":   code_descriptions.get(p["code"], ""),
                    "reason":        "Términos encontrados: " + ", ".join(p["matched_terms"]),
                    "confidence":    p["confidence"],
                    "matched_terms": p["matched_terms"],
                    "engine":        "dict",
                }
                for p in predictions
            ],
        },
        {
            "type": "recommendations",
            "content": (
                "Revisar y confirmar los códigos asignados con el equipo médico "
                "antes de registrar el alta."
            ),
        },
    ]}
