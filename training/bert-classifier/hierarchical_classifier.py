"""
Integración del Clasificador Jerárquico CIE-10 en ai_engine

Este archivo muestra cómo cargar y usar los modelos entrenados
desde ai_engine/main.py para servir predicciones via API.
"""

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer
import json
from pathlib import Path
import numpy as np
from typing import List, Tuple, Dict


# ==================== CLASES DEL MODELO ====================

class ChapterClassifier(nn.Module):
    """Clasificador de Capítulos CIE-10 (Nivel 1)"""

    def __init__(self, model_name, num_chapters, dropout=0.1):
        super().__init__()
        self.roberta = AutoModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(self.roberta.config.hidden_size, num_chapters)

    def forward(self, input_ids, attention_mask):
        outputs = self.roberta(
            input_ids=input_ids,
            attention_mask=attention_mask
        )
        pooled_output = outputs.last_hidden_state[:, 0, :]
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier(pooled_output)
        return logits


class CodeClassifier(nn.Module):
    """Clasificador de Códigos CIE-10 específicos (Nivel 2)"""

    def __init__(self, model_name, num_codes, dropout=0.1):
        super().__init__()
        self.roberta = AutoModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(self.roberta.config.hidden_size, num_codes)

    def forward(self, input_ids, attention_mask):
        outputs = self.roberta(
            input_ids=input_ids,
            attention_mask=attention_mask
        )
        pooled_output = outputs.last_hidden_state[:, 0, :]
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier(pooled_output)
        return logits


# ==================== FUNCIONES AUXILIARES ====================

def extract_chapter_from_code(code: str) -> str:
    """Extraer capítulo CIE-10 del código"""
    if not code or len(code) == 0:
        return None

    first_letter = code[0].upper()

    # Mapeo simplificado (ver notebook para versión completa)
    chapter_map = {
        'A': 'I', 'B': 'I',
        'C': 'II', 'D': 'II',  # Simplificado
        'E': 'IV',
        'F': 'V',
        'G': 'VI',
        'H': 'VII',  # Simplificado
        'I': 'IX',
        'J': 'X',
        'K': 'XI',
        'L': 'XII',
        'M': 'XIII',
        'N': 'XIV',
        'O': 'XV',
        'P': 'XVI',
        'Q': 'XVII',
        'R': 'XVIII',
        'S': 'XIX', 'T': 'XIX',
        'V': 'XX', 'W': 'XX', 'X': 'XX', 'Y': 'XX',
        'Z': 'XXI'
    }

    return chapter_map.get(first_letter)


# ==================== CLASE PRINCIPAL ====================

class HierarchicalCIE10Classifier:
    """Clasificador jerárquico de 2 niveles para CIE-10"""

    def __init__(self, model_dir: str, device: str = 'cpu'):
        """
        Args:
            model_dir: Directorio con los modelos exportados (ej: 'ai_engine/model')
            device: 'cpu' o 'cuda'
        """
        self.device = torch.device(device)
        model_path = Path(model_dir)

        # Cargar configuración
        with open(model_path / 'config.json', 'r') as f:
            self.config = json.load(f)

        # Cargar capítulos CIE-10
        with open(model_path / 'cie10_chapters.json', 'r', encoding='utf-8') as f:
            self.chapters = json.load(f)

        # Cargar tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(self.config['model_name'])

        # Cargar Nivel 1 (Capítulos)
        checkpoint_level1 = torch.load(
            model_path / 'chapter_classifier.pt',
            map_location=self.device
        )
        self.chapter_to_idx = checkpoint_level1['chapter_to_idx']
        self.idx_to_chapter = checkpoint_level1['idx_to_chapter']

        self.chapter_model = ChapterClassifier(
            self.config['model_name'],
            len(self.chapter_to_idx),
            dropout=0.1
        )
        self.chapter_model.load_state_dict(checkpoint_level1['model_state_dict'])
        self.chapter_model.to(self.device)
        self.chapter_model.eval()

        # Cargar Nivel 2 (Códigos)
        checkpoint_level2 = torch.load(
            model_path / 'code_classifier.pt',
            map_location=self.device
        )
        self.code_to_idx = checkpoint_level2['code_to_idx']
        self.idx_to_code = checkpoint_level2['idx_to_code']

        self.code_model = CodeClassifier(
            self.config['model_name'],
            len(self.code_to_idx),
            dropout=0.1
        )
        self.code_model.load_state_dict(checkpoint_level2['model_state_dict'])
        self.code_model.to(self.device)
        self.code_model.eval()

        # Crear mapeo código -> capítulo
        self.code_to_chapter = {}
        for code in self.code_to_idx.keys():
            chapter = extract_chapter_from_code(code)
            if chapter:
                self.code_to_chapter[code] = chapter

        print(f"✅ Clasificador jerárquico cargado")
        print(f"   Nivel 1: {len(self.chapter_to_idx)} capítulos")
        print(f"   Nivel 2: {len(self.code_to_idx)} códigos")
        print(f"   Device: {self.device}")

    def predict(self, text: str, top_k: int = 10) -> List[Dict[str, any]]:
        """
        Predicción jerárquica

        Args:
            text: Texto del informe médico
            top_k: Número de códigos a retornar

        Returns:
            List[Dict] con formato:
            [
                {
                    'code': 'I10',
                    'probability': 0.92,
                    'chapter': 'IX',
                    'chapter_name': 'Enfermedades del sistema circulatorio'
                },
                ...
            ]
        """
        # Tokenizar
        encoding = self.tokenizer(
            text,
            max_length=self.config['max_length'],
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )

        input_ids = encoding['input_ids'].to(self.device)
        attention_mask = encoding['attention_mask'].to(self.device)

        # === NIVEL 1: Predecir capítulos ===
        with torch.no_grad():
            chapter_logits = self.chapter_model(input_ids, attention_mask)
            chapter_probs = torch.sigmoid(chapter_logits).cpu().numpy()[0]

        # Top-K capítulos
        top_chapter_indices = np.argsort(chapter_probs)[::-1][:self.config['top_k_chapters']]
        top_chapters = [
            self.idx_to_chapter[str(idx)] for idx in top_chapter_indices
            if chapter_probs[idx] > self.config['threshold_level1']
        ]

        if not top_chapters:
            top_chapters = [self.idx_to_chapter[str(top_chapter_indices[0])]]

        # === NIVEL 2: Predecir códigos ===
        with torch.no_grad():
            code_logits = self.code_model(input_ids, attention_mask)
            code_probs = torch.sigmoid(code_logits).cpu().numpy()[0]

        # Filtrar códigos por capítulos seleccionados
        predictions = []
        for code_idx, prob in enumerate(code_probs):
            code = self.idx_to_code[str(code_idx)]
            code_chapter = self.code_to_chapter.get(code)

            if code_chapter in top_chapters and prob > self.config['threshold_level2']:
                predictions.append({
                    'code': code,
                    'probability': float(prob),
                    'chapter': code_chapter,
                    'chapter_name': self.chapters.get(code_chapter, {}).get('name', 'N/A')
                })

        # Ordenar por probabilidad
        predictions.sort(key=lambda x: x['probability'], reverse=True)
        return predictions[:top_k]


# ==================== EJEMPLO DE USO ====================

if __name__ == '__main__':
    # Cargar clasificador
    classifier = HierarchicalCIE10Classifier(
        model_dir='../model',
        device='cpu'  # o 'cuda' si tienes GPU
    )

    # Texto de prueba
    text = """
    Paciente de 65 años con antecedentes de hipertensión arterial esencial,
    diabetes mellitus tipo 2 en tratamiento con metformina, y cardiopatía
    isquémica crónica. Refiere dolor precordial opresivo de inicio súbito
    hace 2 horas, irradiado a brazo izquierdo. ECG muestra elevación del
    segmento ST en derivaciones anteriores. Se diagnostica infarto agudo
    de miocardio con elevación del ST.
    """

    # Predicción
    print("\n" + "="*60)
    print("🔮 PREDICCIÓN JERÁRQUICA CIE-10")
    print("="*60)

    predictions = classifier.predict(text, top_k=5)

    for i, pred in enumerate(predictions, 1):
        print(f"\n{i}. {pred['code']} (Cap. {pred['chapter']})")
        print(f"   Probabilidad: {pred['probability']:.4f}")
        print(f"   Capítulo: {pred['chapter_name']}")


# ==================== INTEGRACIÓN EN FASTAPI ====================

"""
# En ai_engine/main.py:

from fastapi import FastAPI
from hierarchical_classifier import HierarchicalCIE10Classifier

app = FastAPI()

# Cargar modelo al iniciar
@app.on_event("startup")
async def load_model():
    global classifier
    classifier = HierarchicalCIE10Classifier(
        model_dir='model',
        device='cpu'
    )

@app.post("/predict")
async def predict(request: PredictRequest):
    '''Endpoint de predicción'''
    text = request.text
    predictions = classifier.predict(text, top_k=10)

    return {
        "predictions": predictions,
        "model": "hierarchical-roberta-bsc",
        "timestamp": datetime.now().isoformat()
    }
"""
