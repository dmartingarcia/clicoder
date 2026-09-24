import asyncio
import json
import random

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="CIE-10 AI Engine", version="1.0.0")

KEYWORD_CODES: list[tuple[list[str], dict]] = [
    (
        ["hipertensión", "presión arterial", "hta", "hipertenso"],
        {
            "code": "I10",
            "description": "Hipertensión esencial (primaria)",
            "reason": "Detección de términos relacionados con hipertensión arterial",
            "confidence": 0.94,
        },
    ),
    (
        ["diabetes", "glucosa", "insulina", "diabético", "hiperglucemia"],
        {
            "code": "E11.9",
            "description": "Diabetes mellitus tipo 2 sin complicaciones",
            "reason": "Detección de términos relacionados con diabetes mellitus",
            "confidence": 0.91,
        },
    ),
    (
        ["infarto", "iam", "coronario", "miocardio", "isquemia"],
        {
            "code": "I21.9",
            "description": "Infarto agudo de miocardio, no especificado",
            "reason": "Detección de términos cardíacos agudos",
            "confidence": 0.97,
        },
    ),
    (
        ["neumonía", "neumonia", "pulmonar", "bronconeumonía", "consolidación"],
        {
            "code": "J18.9",
            "description": "Neumonía, no especificada",
            "reason": "Detección de términos relacionados con infección pulmonar",
            "confidence": 0.89,
        },
    ),
    (
        ["fractura", "hueso", "roto", "óseo", "fémur", "tibia"],
        {
            "code": "S72.9",
            "description": "Fractura de fémur, parte no especificada",
            "reason": "Detección de términos relacionados con fractura ósea",
            "confidence": 0.85,
        },
    ),
    (
        ["depresión", "ansied", "ansiedad", "mental", "psiquiátrico", "tristeza"],
        {
            "code": "F32.9",
            "description": "Episodio depresivo, no especificado",
            "reason": "Detección de términos relacionados con salud mental",
            "confidence": 0.82,
        },
    ),
    (
        ["asma", "bronquitis", "disnea", "sibilancias", "broncoespasmo"],
        {
            "code": "J45.9",
            "description": "Asma, no especificada",
            "reason": "Detección de términos relacionados con patología respiratoria obstructiva",
            "confidence": 0.88,
        },
    ),
    (
        ["insuficiencia renal", "renal", "riñón", "creatinina", "diálisis"],
        {
            "code": "N18.9",
            "description": "Enfermedad renal crónica, no especificada",
            "reason": "Detección de términos relacionados con función renal",
            "confidence": 0.86,
        },
    ),
    (
        ["dolor abdominal", "abdomen", "gástrico", "gastritis", "úlcera"],
        {
            "code": "K25.9",
            "description": "Úlcera gástrica, no especificada",
            "reason": "Detección de términos relacionados con patología gastrointestinal",
            "confidence": 0.80,
        },
    ),
    (
        ["accidente cerebrovascular", "acv", "ictus", "derrame", "neurológico"],
        {
            "code": "I64",
            "description": "Accidente vascular encefálico, no especificado",
            "reason": "Detección de términos relacionados con evento cerebrovascular",
            "confidence": 0.95,
        },
    ),
    (
        ["obesidad", "sobrepeso", "bmi", "imc", "obeso"],
        {
            "code": "E66.9",
            "description": "Obesidad, no especificada",
            "reason": "Detección de términos relacionados con exceso de peso",
            "confidence": 0.87,
        },
    ),
    (
        ["hipotiroidismo", "tiroides", "tiroxina", "tsh"],
        {
            "code": "E03.9",
            "description": "Hipotiroidismo, no especificado",
            "reason": "Detección de términos relacionados con función tiroidea",
            "confidence": 0.83,
        },
    ),
]

FALLBACK_CODES = [
    {
        "code": "Z03.89",
        "description": "Encuentro para observación por sospecha de otras enfermedades y afecciones descartadas",
        "reason": "No se detectaron palabras clave específicas en el texto",
        "confidence": 0.50,
    },
]


def _add_relative_confidence(codes: list[dict]) -> list[dict]:
    """Normalización min-max de las confianzas dentro del conjunto (igual que producción)."""
    if len(codes) < 2:
        for c in codes:
            c["relative_confidence"] = 1.0
        return codes
    values = [c["confidence"] for c in codes]
    lo, hi = min(values), max(values)
    spread = hi - lo
    for c in codes:
        c["relative_confidence"] = (
            round((c["confidence"] - lo) / spread, 4) if spread > 1e-6 else 1.0
        )
    return codes


def analyze_text(text: str, engine: str = "bert") -> list[dict]:
    text_lower = text.lower()
    matched: list[dict] = []
    seen_codes: set[str] = set()

    for keywords, code_entry in KEYWORD_CODES:
        hits = [kw for kw in keywords if kw in text_lower]
        if hits and code_entry["code"] not in seen_codes:
            item = dict(code_entry)  # copia para no mutar la plantilla compartida
            item["triggers"] = hits
            item["engine"] = engine
            matched.append(item)
            seen_codes.add(code_entry["code"])

    if not matched:
        item = dict(FALLBACK_CODES[0])
        item["triggers"] = []
        item["engine"] = engine
        matched = [item]

    return _add_relative_confidence(matched[:10])


def build_summary(text: str, codes: list[dict]) -> str:
    code_list = ", ".join(c["code"] for c in codes)
    words = len(text.split())
    return (
        f"Informe clínico analizado ({words} palabras). "
        f"Se identificaron {len(codes)} código(s) CIE-10: {code_list}. "
        "El análisis se ha realizado mediante detección de términos clínicos clave."
    )


def build_recommendations(codes: list[dict]) -> str:
    if not codes or codes[0]["code"] == "Z03.89":
        return "No se identificaron patologías específicas. Se recomienda revisión manual del informe."

    parts = []
    code_set = {c["code"] for c in codes}

    if "I10" in code_set or "I21.9" in code_set or "I64" in code_set:
        parts.append(
            "Valorar seguimiento cardiológico y control de factores de riesgo cardiovascular."
        )
    if "E11.9" in code_set:
        parts.append(
            "Monitorizar glucemia periódicamente y ajustar tratamiento antidiabético si procede."
        )
    if "J18.9" in code_set or "J45.9" in code_set:
        parts.append(
            "Evaluar función respiratoria y considerar derivación a neumología si hay progresión."
        )
    if "F32.9" in code_set:
        parts.append(
            "Considerar evaluación psiquiátrica y seguimiento en salud mental."
        )
    if not parts:
        parts.append(
            "Revisar los códigos asignados con el equipo clínico y confirmar el diagnóstico."
        )

    return " ".join(parts)


class AnalysisRequest(BaseModel):
    text: str
    engine: str = "bert"


class TokenCountRequest(BaseModel):
    text: str


class SummarizeRequest(BaseModel):
    text: str
    system_prompt: str | None = None
    user_prompt: str | None = None
    mode: str = "summary"


@app.get("/", summary="Health check")
def health_check():
    return {
        "status": "online",
        "model": "MOCK-no-GPU",
        "model_loaded": True,
        "dict_loaded": True,
        "summarizer_model": "mock",
        "summarizer_loaded": True,
    }


@app.post("/count-tokens", summary="Contar tokens (aproximado, mock)")
async def count_tokens(request: TokenCountRequest):
    # Aproximación sencilla para el contador del frontend.
    words = len(request.text.split())
    return {"token_count": int(words / 0.75) + 2}


@app.post("/predict", summary="Predecir códigos CIE-10 (mock)")
async def predict_codes(request: AnalysisRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="El texto no puede estar vacío.")
    await asyncio.sleep(random.uniform(0.3, 0.9))
    engine = request.engine if request.engine in ("bert", "dict") else "bert"
    codes = analyze_text(text, engine=engine)
    return {"cards": [{"type": "codes", "content": codes}], "model_version": "mock@000000000000"}


@app.post("/summarize/stream", summary="Resumen médico en streaming (NDJSON, mock)")
async def summarize_stream(request: SummarizeRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="El texto no puede estar vacío.")

    async def _stream():
        summary = build_summary(text, analyze_text(text))
        for word in summary.split(" "):
            await asyncio.sleep(0.02)
            yield json.dumps({"token": word + " "}) + "\n"
        yield json.dumps({"done": True}) + "\n"

    return StreamingResponse(_stream(), media_type="application/x-ndjson")
