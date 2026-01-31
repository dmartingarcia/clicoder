# ai_engine/main.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI(title="CIE-10 AI Engine")

class AnalysisRequest(BaseModel):
    text: str

@app.get("/")
def health_check():
    return {"status": "online", "model": "RoBERTa-Medical-ES"}

@app.post("/predict")
async def predict_codes(request: AnalysisRequest):
    # TODO: Aquí irá la inferencia real con el modelo de Hugging Face
    # Por ahora devolvemos un Mock para probar la conexión con Elixir
    mock_codes = [
        {"code": "I10", "description": "Hipertensión esencial (primaria)", "reason": "Detección de 'presión arterial alta'"},
        {"code": "E11.9", "description": "Diabetes mellitus tipo 2", "reason": "Referencia a 'niveles de glucosa elevados'"}
    ]
    return {"codes": mock_codes}
