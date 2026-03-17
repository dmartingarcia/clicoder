import asyncio
import random
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="CIE-10 AI Engine (MOCK)", version="mock-2.0.0")

KEYWORD_CODES: list[tuple[list[str], dict]] = [
    (
        ["hipertensión", "presión arterial", "hta", "hipertenso"],
        {"code": "I10", "description": "Hipertensión esencial (primaria)", "reason": "Detección de términos relacionados con hipertensión arterial", "confidence": 0.94},
    ),
    (
        ["diabetes", "glucosa", "insulina", "diabético", "hiperglucemia"],
        {"code": "E11.9", "description": "Diabetes mellitus tipo 2 sin complicaciones", "reason": "Detección de términos relacionados con diabetes mellitus", "confidence": 0.91},
    ),
    (
        ["infarto", "iam", "coronario", "miocardio", "isquemia"],
        {"code": "I21.9", "description": "Infarto agudo de miocardio, no especificado", "reason": "Detección de términos cardíacos agudos", "confidence": 0.97},
    ),
    (
        ["neumonía", "neumonia", "pulmonar", "bronconeumonía", "consolidación"],
        {"code": "J18.9", "description": "Neumonía, no especificada", "reason": "Detección de términos relacionados con infección pulmonar", "confidence": 0.89},
    ),
    (
        ["fractura", "hueso", "roto", "óseo", "fémur", "tibia"],
        {"code": "S72.9", "description": "Fractura de fémur, parte no especificada", "reason": "Detección de términos relacionados con fractura ósea", "confidence": 0.85},
    ),
    (
        ["depresión", "ansied", "ansiedad", "mental", "psiquiátrico", "tristeza"],
        {"code": "F32.9", "description": "Episodio depresivo, no especificado", "reason": "Detección de términos relacionados con salud mental", "confidence": 0.82},
    ),
    (
        ["asma", "bronquitis", "disnea", "sibilancias", "broncoespasmo"],
        {"code": "J45.9", "description": "Asma, no especificada", "reason": "Detección de términos relacionados con patología respiratoria obstructiva", "confidence": 0.88},
    ),
    (
        ["insuficiencia renal", "renal", "riñón", "creatinina", "diálisis"],
        {"code": "N18.9", "description": "Enfermedad renal crónica, no especificada", "reason": "Detección de términos relacionados con función renal", "confidence": 0.86},
    ),
    (
        ["dolor abdominal", "abdomen", "gástrico", "gastritis", "úlcera"],
        {"code": "K25.9", "description": "Úlcera gástrica, no especificada", "reason": "Detección de términos relacionados con patología gastrointestinal", "confidence": 0.80},
    ),
    (
        ["accidente cerebrovascular", "acv", "ictus", "derrame", "neurológico"],
        {"code": "I64", "description": "Accidente vascular encefálico, no especificado", "reason": "Detección de términos relacionados con evento cerebrovascular", "confidence": 0.95},
    ),
    (
        ["obesidad", "sobrepeso", "bmi", "imc", "obeso"],
        {"code": "E66.9", "description": "Obesidad, no especificada", "reason": "Detección de términos relacionados con exceso de peso", "confidence": 0.87},
    ),
    (
        ["hipotiroidismo", "tiroides", "tiroxina", "tsh"],
        {"code": "E03.9", "description": "Hipotiroidismo, no especificado", "reason": "Detección de términos relacionados con función tiroidea", "confidence": 0.83},
    ),
]

FALLBACK_CODES = [
    {"code": "Z03.89", "description": "Encuentro para observación por sospecha de otras enfermedades y afecciones descartadas", "reason": "No se detectaron palabras clave específicas en el texto", "confidence": 0.50},
]


def analyze_text(text: str) -> list[dict]:
    text_lower = text.lower()
    matched: list[dict] = []
    seen_codes: set[str] = set()

    for keywords, code_entry in KEYWORD_CODES:
        if any(kw in text_lower for kw in keywords):
            code = code_entry["code"]
            if code not in seen_codes:
                matched.append(code_entry)
                seen_codes.add(code)

    if not matched:
        matched = FALLBACK_CODES.copy()

    return matched[:5]


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
        parts.append("Valorar seguimiento cardiológico y control de factores de riesgo cardiovascular.")
    if "E11.9" in code_set:
        parts.append("Monitorizar glucemia periódicamente y ajustar tratamiento antidiabético si procede.")
    if "J18.9" in code_set or "J45.9" in code_set:
        parts.append("Evaluar función respiratoria y considerar derivación a neumología si hay progresión.")
    if "F32.9" in code_set:
        parts.append("Considerar evaluación psiquiátrica y seguimiento en salud mental.")
    if not parts:
        parts.append("Revisar los códigos asignados con el equipo clínico y confirmar el diagnóstico.")

    return " ".join(parts)


class AnalysisRequest(BaseModel):
    text: str


@app.get("/")
def health_check():
    return {"status": "online", "model": "MOCK-no-GPU", "mode": "development"}


@app.post("/predict")
async def predict_codes(request: AnalysisRequest):
    await asyncio.sleep(random.uniform(0.3, 0.9))

    codes = analyze_text(request.text)

    cards = [
        {
            "type": "summary",
            "content": build_summary(request.text, codes),
        },
        {
            "type": "codes",
            "content": codes,
        },
        {
            "type": "recommendations",
            "content": build_recommendations(codes),
        },
    ]

    # Legacy field kept for backwards compatibility
    return {"cards": cards, "codes": codes}
