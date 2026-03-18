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
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("cie10_engine")
logging.basicConfig(level=logging.INFO)

# Globals poblados en startup
classifier        = None
code_descriptions: Dict[str, str] = {}


# ==================== LIFESPAN ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    global classifier, code_descriptions

    model_dir = os.environ.get("MODEL_DIR", "./model")
    device    = os.environ.get("DEVICE", "cpu")

    if not os.path.isdir(model_dir):
        logger.warning(
            "MODEL_DIR '%s' no existe — el motor arranca sin modelo. "
            "/predict devolverá 503 hasta que se entrene y monte el modelo.",
            model_dir,
        )
    else:
        try:
            from classifier import CIE10Classifier, load_code_descriptions
            logger.info("Cargando modelo desde '%s' en device='%s' …", model_dir, device)
            classifier        = CIE10Classifier(model_dir=model_dir, device=device)
            code_descriptions = load_code_descriptions(model_dir)
            logger.info(
                "Modelo cargado. %d descripciones de códigos disponibles.",
                len(code_descriptions),
            )
        except Exception as exc:
            logger.warning(
                "No se pudo cargar el modelo desde '%s': %s",
                model_dir, exc,
            )
            classifier = None

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


# ==================== ENDPOINTS ====================

@app.get("/", summary="Health check")
def health_check():
    return {
        "status":       "online",
        "model":        "rigoberta-cie10-flat",
        "model_loaded": classifier is not None,
    }


@app.post("/predict", summary="Predecir códigos CIE-10")
async def predict_codes(request: AnalysisRequest):
    if classifier is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "Modelo no cargado. Entrena el modelo con train.py y monta el directorio model/."},
        )

    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="El texto no puede estar vacío.")

    # Inferencia fuera del event loop (operación bloqueante)
    predictions = await asyncio.to_thread(
        classifier.predict,
        text,
        10,
        code_descriptions or None,
    )

    # ---- Construir cards ----
    word_count = len(text.split())
    n_codes    = len(predictions)
    codes_str  = ", ".join(p["code"] for p in predictions) if predictions else "ninguno"

    cards = [
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
    ]

    return {"cards": cards}
