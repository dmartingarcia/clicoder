from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="CIE-10 AI Engine")


class AnalysisRequest(BaseModel):
    text: str


@app.get("/")
def health_check():
    return {"status": "online", "model": "RoBERTa-Medical-ES"}


@app.post("/predict")
async def predict_codes(request: AnalysisRequest):
    # TODO: replace with real HuggingFace model inference
    codes = [
        {"code": "I10", "description": "Hipertensión esencial (primaria)", "reason": "Detección de 'presión arterial alta'", "confidence": 0.94},
        {"code": "E11.9", "description": "Diabetes mellitus tipo 2", "reason": "Referencia a 'niveles de glucosa elevados'", "confidence": 0.91},
    ]

    words = len(request.text.split())
    code_list = ", ".join(c["code"] for c in codes)

    cards = [
        {
            "type": "summary",
            "content": f"Informe clínico analizado ({words} palabras). Se identificaron {len(codes)} código(s) CIE-10: {code_list}.",
        },
        {
            "type": "codes",
            "content": codes,
        },
        {
            "type": "recommendations",
            "content": "Valorar seguimiento clínico y confirmar los códigos asignados con el equipo médico.",
        },
    ]

    return {"cards": cards, "codes": codes}
