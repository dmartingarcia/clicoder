# Carga el modelo entrenado con train.py y expone CIE10Classifier.predict().
# Una sola pasada forward produce probabilidades para todos los ~1767 códigos a la vez.

import json
import sys
from pathlib import Path

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer

# letra inicial → capítulo CIE-10 (número romano)
CHAPTER_MAP = {
    "A": "I",
    "B": "I",
    "C": "II",
    "D": "II",
    "E": "IV",
    "F": "V",
    "G": "VI",
    "H": "VII",
    "I": "IX",
    "J": "X",
    "K": "XI",
    "L": "XII",
    "M": "XIII",
    "N": "XIV",
    "O": "XV",
    "P": "XVI",
    "Q": "XVII",
    "R": "XVIII",
    "S": "XIX",
    "T": "XIX",
    "V": "XX",
    "W": "XX",
    "X": "XX",
    "Y": "XX",
    "Z": "XXI",
}


def _extract_chapter(code: str) -> str | None:
    return CHAPTER_MAP.get(code[0].upper()) if code else None


def load_code_descriptions(model_dir: str) -> dict[str, str]:
    """Carga code_descriptions.json si existe; devuelve {} en caso contrario."""
    path = Path(model_dir) / "code_descriptions.json"
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[warn] No se pudo cargar code_descriptions.json: {e}")
        return {}


class _FlatClassifier(nn.Module):
    def __init__(self, model_name: str, num_codes: int, dropout: float = 0.1):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(self.encoder.config.hidden_size, num_codes)

    def forward(self, input_ids, attention_mask):
        out = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        cls = self.dropout(out.last_hidden_state[:, 0, :])
        return self.classifier(cls)


class CIE10Classifier:
    """Clasificador plano multi-label para CIE-10."""

    def __init__(self, model_dir: str, device: str = "cpu"):
        self.device = torch.device(device)
        model_path = Path(model_dir)

        # Config
        with open(model_path / "config.json") as f:
            self.config = json.load(f)

        # Capítulos (para display)
        chapters_path = model_path / "cie10_chapters.json"
        self.chapters: dict = {}
        if chapters_path.exists():
            with open(chapters_path, encoding="utf-8") as f:
                self.chapters = json.load(f)

        # Tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(self.config["model_name"])

        # Checkpoint
        model_file = self.config.get("model_file", "classifier.pt")
        ckpt = torch.load(
            model_path / model_file,
            map_location=self.device,
            weights_only=False,
        )
        self.code_to_idx: dict[str, int] = ckpt["code_to_idx"]
        self.idx_to_code: dict[str, str] = ckpt["idx_to_code"]

        self.model = _FlatClassifier(
            self.config["model_name"],
            num_codes=len(self.code_to_idx),
        )
        self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.to(self.device)
        self.model.eval()

        # Thresholds por clase (generados en entrenamiento)
        self.per_class_thresholds: list[float] | None = None
        thresholds_file = self.config.get("thresholds_file")
        if thresholds_file:
            thr_path = model_path / thresholds_file
            if thr_path.exists():
                with open(thr_path, encoding="utf-8") as f:
                    thr_data = json.load(f)
                self.per_class_thresholds = thr_data.get("per_class_thresholds")

        print(
            f"CIE10Classifier cargado: {len(self.code_to_idx)} códigos · device={self.device}"
        )

    def predict(
        self,
        text: str,
        top_k: int = 10,
        code_descriptions: dict[str, str] | None = None,
        threshold: float | None = None,
    ) -> list[dict]:
        """
        Clasifica un texto clínico y devuelve los códigos CIE-10 más probables.

        Parámetros
        ----------
        text              : Informe clínico en español.
        top_k             : Número máximo de códigos a devolver.
        code_descriptions : dict code → descripción (opcional).
        threshold         : Umbral mínimo de probabilidad.
                            Si None, usa el valor de config.json (por defecto 0.5).

        Devuelve
        --------
        Lista de dicts ordenados por probabilidad descendente:
            {
                "code":         "I10",
                "probability":  0.92,
                "chapter":      "IX",
                "chapter_name": "Enfermedades del sistema circulatorio",
                "description":  "Hipertensión esencial (primaria)"  # si se pasa
            }
        """
        if threshold is None:
            threshold = float(self.config.get("threshold", 0.5))

        enc = self.tokenizer(
            text,
            max_length=self.config["max_length"],
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        input_ids = enc["input_ids"].to(self.device)
        attention_mask = enc["attention_mask"].to(self.device)

        with torch.no_grad():
            logits = self.model(input_ids, attention_mask)
            probs = torch.sigmoid(logits).cpu().numpy()[0]

        # Recoger predicciones por encima del umbral (por clase si disponible)
        predictions = []
        for idx, prob in enumerate(probs):
            thr = (
                self.per_class_thresholds[idx]
                if self.per_class_thresholds is not None
                else threshold
            )
            if prob < thr:
                continue
            code = self.idx_to_code[str(idx)]
            chapter = _extract_chapter(code)
            entry = {
                "code": code,
                "probability": float(prob),
                "chapter": chapter or "",
                "chapter_name": (
                    self.chapters.get(chapter or "", {}).get("name", "")
                    if chapter
                    else ""
                ),
            }
            if code_descriptions is not None:
                entry["description"] = code_descriptions.get(code, "")
            predictions.append(entry)

        # Priorizar hijos sobre padres: si K13.0 está predicho, eliminar K13
        codes_set = {p["code"] for p in predictions}
        predictions = [
            p
            for p in predictions
            if not any(
                other.startswith(p["code"]) and other != p["code"]
                for other in codes_set
            )
        ]

        predictions.sort(key=lambda x: x["probability"], reverse=True)
        return predictions[:top_k]


if __name__ == "__main__":
    model_dir = sys.argv[1] if len(sys.argv) > 1 else "./model"
    clf = CIE10Classifier(model_dir=model_dir, device="cpu")
    descs = load_code_descriptions(model_dir)

    text = (
        "Paciente de 65 años con hipertensión arterial esencial, diabetes mellitus "
        "tipo 2 y cardiopatía isquémica crónica. Dolor precordial opresivo irradiado "
        "a brazo izquierdo. ECG: elevación del segmento ST en derivaciones anteriores. "
        "Diagnóstico: infarto agudo de miocardio con elevación del ST (SCAEST)."
    )

    results = clf.predict(text, top_k=5, code_descriptions=descs)
    print("\nPredicciones:")
    for r in results:
        print(
            f"  {r['code']:10s}  p={r['probability']:.3f}  "
            f"cap={r['chapter']:5s}  {r.get('description', '')}"
        )
