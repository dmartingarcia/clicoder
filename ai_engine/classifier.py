# Carga el modelo entrenado con train.py y expone CIE10Classifier.predict().
# Una sola pasada forward produce probabilidades para todos los ~1767 códigos a la vez.

import json
import logging
import sys
from pathlib import Path

try:
    import sentry_sdk as _sentry
except ImportError:
    _sentry = None  # type: ignore[assignment]

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer

logger = logging.getLogger("cie10_engine")

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
        if _sentry:
            _sentry.capture_exception(e)
        logger.warning("No se pudo cargar code_descriptions.json: %s", e)
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

        print(f"CIE10Classifier cargado: {len(self.code_to_idx)} códigos · device={self.device}")

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
                    self.chapters.get(chapter or "", {}).get("name", "") if chapter else ""
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
            if not any(other.startswith(p["code"]) and other != p["code"] for other in codes_set)
        ]

        predictions.sort(key=lambda x: x["probability"], reverse=True)
        return predictions[:top_k]

    def explain(
        self,
        text: str,
        code_indices: list[int],
        top_k: int = 5,
        batch_size: int = 16,
    ) -> dict[int, list[str]]:
        """Atribución por enmascaramiento (masking perturbation) por código predicho.

        Para cada palabra del texto, la sustituye por [MASK] y mide la caída en el
        logit del código k. Las palabras que más reducen el logit son los verdaderos
        triggers del modelo para ese código concreto.

        Sólo procesa palabras de ≥ 4 caracteres para evitar ruido de stopwords.
        Los forward passes se agrupan en batches para eficiencia.
        """
        import string as _string

        if not code_indices:
            return {}

        mask_id = self.tokenizer.mask_token_id
        if mask_id is None:
            return {idx: [] for idx in code_indices}

        enc = self.tokenizer(
            text,
            max_length=self.config["max_length"],
            truncation=True,
        )
        word_ids = enc.word_ids()  # posición token → índice de palabra (None para especiales)
        input_ids_list = enc["input_ids"]
        attention_mask_list = enc["attention_mask"]

        # Agrupar posiciones de token por palabra
        word_positions: dict[int, list[int]] = {}
        for pos, wid in enumerate(word_ids):
            if wid is not None:
                word_positions.setdefault(wid, []).append(pos)

        # Palabras de origen para display
        raw_words = text.split()

        # Filtrar palabras cortas o de puntuación pura
        candidates = [
            wid
            for wid in word_positions
            if wid < len(raw_words) and len(raw_words[wid].strip(_string.punctuation)) >= 4
        ]

        if not candidates:
            return {idx: [] for idx in code_indices}

        # Padding hasta max_length para hacer batching uniforme
        max_len = self.config["max_length"]
        pad_id = self.tokenizer.pad_token_id or 0
        seq_len = len(input_ids_list)
        padded_ids = input_ids_list + [pad_id] * (max_len - seq_len)
        padded_mask = attention_mask_list + [0] * (max_len - seq_len)

        base_ids = torch.tensor([padded_ids], dtype=torch.long, device=self.device)
        base_mask = torch.tensor([padded_mask], dtype=torch.long, device=self.device)

        try:
            # Logits de referencia (sin máscara)
            with torch.no_grad():
                baseline = self.model(base_ids, base_mask)[0, code_indices].cpu()  # [K]

            # importance[wid][k] = caída en logit_k al enmascarar wid
            importance: dict[int, torch.Tensor] = {}

            for batch_start in range(0, len(candidates), batch_size):
                batch_wids = candidates[batch_start : batch_start + batch_size]
                B = len(batch_wids)
                batch_ids = base_ids.repeat(B, 1).clone()

                for i, wid in enumerate(batch_wids):
                    for pos in word_positions[wid]:
                        if pos < max_len:
                            batch_ids[i, pos] = mask_id

                batch_mask = base_mask.repeat(B, 1)

                with torch.no_grad():
                    logits = self.model(batch_ids, batch_mask)[:, code_indices].cpu()  # [B, K]

                for i, wid in enumerate(batch_wids):
                    importance[wid] = (baseline - logits[i]).clamp(min=0)  # [K]

            # Por cada código, ordenar palabras por importancia y devolver top_k
            results: dict[int, list[str]] = {}
            for k_pos, code_idx in enumerate(code_indices):
                scored = sorted(
                    candidates,
                    key=lambda wid: importance[wid][k_pos].item(),
                    reverse=True,
                )
                words = [
                    raw_words[wid].strip(_string.punctuation)
                    for wid in scored[: top_k * 2]  # margen para filtrar residuos
                    if importance[wid][k_pos].item() > 0
                    and len(raw_words[wid].strip(_string.punctuation)) >= 4
                ]
                results[code_idx] = words[:top_k]

            return results

        except Exception as exc:
            if _sentry:
                _sentry.capture_exception(exc)
            logger.warning("explain() falló para %d códigos: %s", len(code_indices), exc)
            return {idx: [] for idx in code_indices}


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
