"""Carga el modelo entrenado con train.py y expone CIE10Classifier.

Una sola pasada del encoder produce probabilidades para los ~1767 códigos a la vez.
Contiene además el registro de estrategias de atribución que usa /explain.
"""

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import sentry_sdk as _sentry
except ImportError:
    _sentry = None  # type: ignore[assignment]

import numpy as np
import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer

logger = logging.getLogger("cie10_engine")

# Rangos de categoría (3 caracteres) → capítulo CIE-10 (número romano).
# La letra inicial NO basta: la D se reparte entre neoplasias (C00-D49) y enfermedades de
# la sangre (D50-D89), y la H entre ojo (H00-H59) y oído (H60-H95). Mapear solo por letra
# colapsaba los capítulos III y VIII sobre el II y el VII.
CHAPTER_RANGES: list[tuple[str, str, str]] = [
    ("I", "A00", "B99"),  # Enfermedades infecciosas y parasitarias
    ("II", "C00", "D49"),  # Neoplasias
    ("III", "D50", "D89"),  # Sangre y órganos hematopoyéticos
    ("IV", "E00", "E89"),  # Endocrinas, nutricionales y metabólicas
    ("V", "F01", "F99"),  # Trastornos mentales y del comportamiento
    ("VI", "G00", "G99"),  # Sistema nervioso
    ("VII", "H00", "H59"),  # Ojo y anejos
    ("VIII", "H60", "H95"),  # Oído y apófisis mastoides
    ("IX", "I00", "I99"),  # Sistema circulatorio
    ("X", "J00", "J99"),  # Sistema respiratorio
    ("XI", "K00", "K95"),  # Sistema digestivo
    ("XII", "L00", "L99"),  # Piel y tejido subcutáneo
    ("XIII", "M00", "M99"),  # Sistema osteomuscular y tejido conjuntivo
    ("XIV", "N00", "N99"),  # Sistema genitourinario
    ("XV", "O00", "O9A"),  # Embarazo, parto y puerperio
    ("XVI", "P00", "P96"),  # Afecciones del periodo perinatal
    ("XVII", "Q00", "Q99"),  # Malformaciones congénitas
    ("XVIII", "R00", "R99"),  # Síntomas y signos mal definidos
    ("XIX", "S00", "T88"),  # Traumatismos y envenenamientos
    ("XX", "V00", "Y99"),  # Causas externas de morbilidad
    ("XXI", "Z00", "Z99"),  # Factores que influyen en el estado de salud
    ("XXII", "U00", "U85"),  # Códigos para propósitos especiales
]

# Compatibilidad: mapeo por letra para los casos sin ambigüedad. Las letras D y H no
# aparecen aquí a propósito, porque su capítulo depende del número de categoría.
CHAPTER_MAP = {
    letter: chapter
    for chapter, lo, hi in CHAPTER_RANGES
    if lo[0] == hi[0]
    for letter in [lo[0]]
    if lo[0] not in ("D", "H")
}


def _extract_chapter(code: str) -> str | None:
    """Capítulo CIE-10 de un código, resolviendo los rangos que comparten letra inicial."""
    if not code:
        return None
    category = code.strip().upper()[:3].ljust(3, "0")
    for chapter, lo, hi in CHAPTER_RANGES:
        if lo <= category <= hi:
            return chapter
    return None


def load_code_descriptions(model_dir: str) -> dict[str, str]:
    """Carga code_descriptions.json si existe; devuelve {} en caso contrario."""
    path = Path(model_dir) / "code_descriptions.json"
    if not path.exists():
        return {}
    if path.stat().st_size == 0:
        logger.warning("code_descriptions.json está vacío en '%s'", model_dir)
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


# ============================================================================
# Métodos de atribución (explicabilidad)
# ============================================================================
#
# Las tres estrategias responden a la misma pregunta (qué palabras del informe
# sostienen cada código predicho) y devuelven el mismo tipo de respuesta: la caída
# real del logit al enmascarar la palabra. Lo que cambia es a cuántas palabras se
# pregunta, porque preguntar cuesta una pasada del encoder por palabra.
#
# Son versiones sucesivas de la misma funcionalidad, no alternativas equivalentes:
# la exhaustiva es la referencia contra la que se miden las demás, y siempre se puede
# volver a ella si una versión rápida se comporta mal.


@dataclass
class _CtxAtribucion:
    """Estado compartido por los métodos de atribución para una sola consulta."""

    modelo: nn.Module
    base_ids: torch.Tensor
    base_mask: torch.Tensor
    mask_id: int
    word_positions: dict[int, list[int]]
    code_indices: list[int]
    baseline: torch.Tensor
    max_len: int
    batch_size: int

    def caida_al_enmascarar(self, grupos: list[list[int]]) -> torch.Tensor:
        """Cuánto baja el logit de cada código al enmascarar cada grupo de palabras.

        Devuelve [len(grupos), K]. Es la operación que cuesta dinero: una pasada del
        encoder por grupo, agrupadas en lotes.
        """
        salida = []
        for inicio in range(0, len(grupos), self.batch_size):
            trozo = grupos[inicio : inicio + self.batch_size]
            ids = self.base_ids.repeat(len(trozo), 1).clone()
            for i, grupo in enumerate(trozo):
                for wid in grupo:
                    for pos in self.word_positions[wid]:
                        if pos < self.max_len:
                            ids[i, pos] = self.mask_id
            with torch.no_grad():
                logits = self.modelo(ids, self.base_mask.repeat(len(trozo), 1))
                salida.append((self.baseline - logits[:, self.code_indices].cpu()).clamp(min=0))
        return torch.cat(salida, 0) if salida else torch.zeros(0, len(self.code_indices))


def _explicar_exhaustivo(ctx: _CtxAtribucion, candidatas: list[int]) -> dict[int, torch.Tensor]:
    """Pregunta por todas las palabras, una a una.

    Es la versión de referencia: mide exactamente lo que dice medir y no asume nada
    sobre la estructura del problema. También es la más cara, con una pasada del encoder
    por palabra del informe (del orden de 300 en un informe clínico típico), lo que la
    convierte en el componente que domina la latencia del sistema.
    """
    caidas = ctx.caida_al_enmascarar([[w] for w in candidatas])
    return {w: caidas[i] for i, w in enumerate(candidatas)}


def _explicar_divide_y_venceras(
    ctx: _CtxAtribucion, candidatas: list[int], umbral: float = 0.05
) -> dict[int, torch.Tensor]:
    """Enmascara grupos y descarta entero el que no mueve ningún logit.

    Aprovecha que la importancia es dispersa: de las trescientas palabras de un informe,
    las que sostienen un código son un puñado. Si al tapar un grupo entero ningún logit
    se mueve, ninguna palabra de dentro importa y el grupo se descarta sin abrirlo; si
    alguno se mueve, el grupo se parte por la mitad y se repite. Solo las palabras que
    llegan solas a una hoja reciben su medida individual, idéntica a la del exhaustivo.

    El supuesto que introduce es la monotonía de la poda: se asume que un grupo sin efecto
    no esconde palabras con efecto. Puede fallar cuando dos palabras son redundantes entre
    sí (tapar una sola no baja el logit porque la otra sostiene la predicción), motivo por
    el que el umbral se deja bajo y por el que conviene contrastar con el exhaustivo.

    MEDIDO: en este corpus NO compensa. Sobre informes de CodiEsp resulta un 73 % MÁS LENTO
    que el exhaustivo (79,4 s frente a 45,8 s; 218 evaluaciones de grupo frente a 128), y
    además pierde algo de fidelidad. La razón es estructural y no de implementación: el árbol
    de recursión tiene aproximadamente el doble de nodos que hojas, de modo que solo gana si
    la poda dispara a menudo, y aquí casi nunca dispara porque demasiadas palabras mueven el
    logit por encima del umbral. La importancia no es lo bastante dispersa.

    Se conserva en el registro porque el resultado es reproducible y porque en un corpus con
    importancia más concentrada sí ganaría, pero NO debe usarse como método por defecto.
    """
    importancia = {w: torch.zeros(len(ctx.code_indices)) for w in candidatas}
    frontera = [candidatas]
    while frontera:
        caidas = ctx.caida_al_enmascarar(frontera)
        siguiente = []
        for grupo, caida in zip(frontera, caidas, strict=True):
            if caida.max().item() < umbral:
                continue
            if len(grupo) == 1:
                importancia[grupo[0]] = caida
            else:
                mitad = len(grupo) // 2
                siguiente += [grupo[:mitad], grupo[mitad:]]
        frontera = siguiente
    return importancia


def _explicar_gradiente_filtrado(
    ctx: _CtxAtribucion, candidatas: list[int], n_verificar: int = 32
) -> dict[int, torch.Tensor]:
    """El gradiente ordena a quién preguntar; el enmascarado sigue midiendo la respuesta.

    Una única pasada hacia atrás da una estimación barata de la importancia de cada token,
    y con ella se eligen las palabras más prometedoras. Solo esas se enmascaran de verdad,
    de modo que los valores que se reportan siguen siendo caídas reales del logit.

    El gradiente por sí solo se descartó en su momento por producir atribuciones ruidosas
    en una arquitectura de 24 capas. Esa objeción no se aplica aquí: como filtro no
    necesita ser exacto, solo no dejar fuera a las palabras buenas, y cualquier error de
    orden que cometa lo corrige después la medición por enmascarado.
    """
    embeddings = ctx.modelo.encoder.embeddings.word_embeddings
    capturado: dict[str, torch.Tensor] = {}

    def _hook(_mod, _entrada, salida):
        salida.retain_grad()
        capturado["emb"] = salida

    asa = embeddings.register_forward_hook(_hook)
    try:
        ctx.modelo.zero_grad(set_to_none=True)
        logits = ctx.modelo(ctx.base_ids, ctx.base_mask)
        logits[0, ctx.code_indices].sum().backward()
    except RuntimeError as exc:
        # Sin gradiente no hay filtro. Se degrada al exhaustivo en vez de fallar: más lento,
        # pero el usuario recibe su explicación.
        logger.warning("gradiente no disponible, se usa el método exhaustivo: %s", exc)
        ctx.modelo.zero_grad(set_to_none=True)
        return _explicar_exhaustivo(ctx, candidatas)
    finally:
        asa.remove()

    emb = capturado.get("emb")
    if emb is None or emb.grad is None:
        ctx.modelo.zero_grad(set_to_none=True)
        return _explicar_exhaustivo(ctx, candidatas)

    saliencia = (emb.grad * emb).sum(-1).abs()[0].detach().cpu()
    ctx.modelo.zero_grad(set_to_none=True)
    puntuacion = {
        w: float(sum(saliencia[p] for p in ctx.word_positions[w] if p < len(saliencia)))
        for w in candidatas
    }
    mejores = sorted(candidatas, key=lambda w: -puntuacion[w])[:n_verificar]
    caidas = ctx.caida_al_enmascarar([[w] for w in mejores])
    return {w: caidas[i] for i, w in enumerate(mejores)}


METODOS_EXPLAIN = {
    "exhaustivo": _explicar_exhaustivo,
    "divide_y_venceras": _explicar_divide_y_venceras,
    "gradiente_filtrado": _explicar_gradiente_filtrado,
}
EXPLAIN_POR_DEFECTO = "exhaustivo"


class CIE10Classifier:
    """Clasificador plano multi-label para CIE-10."""

    def __init__(self, model_dir: str, device: str = "cpu", overrides: dict | None = None):
        """Carga el modelo indicado en config.json, o el que imponga ``overrides``.

        ``overrides`` permite instanciar un checkpoint concreto sin tocar config.json, que es
        lo que necesita el cambio de modelo en caliente: se construye el clasificador nuevo
        entero y solo cuando ha cargado bien se sustituye al que estaba sirviendo.
        """
        self.device = torch.device(device)
        model_path = Path(model_dir)

        # Config
        with open(model_path / "config.json") as f:
            self.config = json.load(f)
        if overrides:
            self.config = {**self.config, **overrides}

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
        logit_bonus: np.ndarray | None = None,
        score_threshold: float | None = None,
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
        logit_bonus       : Vector (num_codes,) que se suma a los logits antes de ordenar.
                            Sirve para fusionar con otra fuente de evidencia: el diccionario
                            de bloques: sin reentrenar nada. Al activarlo, la ordenación y el
                            filtrado pasan al espacio de puntuación fusionada.
        score_threshold   : Umbral sobre la puntuación fusionada (logit + bonus). Obligatorio
                            junto a logit_bonus: el umbral de probabilidad heredado no sirve,
                            porque la bonificación satura las probabilidades de todo código
                            cuyo bloque haya hecho match.

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
            raw_logits = logits.cpu().numpy()[0]
            probs = torch.sigmoid(logits).cpu().numpy()[0]

        # Fusión: la ordenación pasa al espacio de puntuación, pero la confianza que se
        # reporta sigue siendo la probabilidad del modelo: es la que el usuario interpreta.
        fused = logit_bonus is not None
        scores = raw_logits + logit_bonus if fused else None
        if fused and score_threshold is None:
            raise ValueError("logit_bonus requiere score_threshold: ver docstring")

        # Recoger predicciones por encima del umbral (por clase si disponible)
        predictions = []
        for idx, prob in enumerate(probs):
            if fused:
                if scores[idx] < score_threshold:
                    continue
            else:
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
            if fused:
                entry["score"] = float(scores[idx])
                entry["dict_bonus"] = float(logit_bonus[idx])
            predictions.append(entry)

        # Priorizar hijos sobre padres: si K13.0 está predicho, eliminar K13
        codes_set = {p["code"] for p in predictions}
        predictions = [
            p
            for p in predictions
            if not any(other.startswith(p["code"]) and other != p["code"] for other in codes_set)
        ]

        predictions.sort(key=lambda x: x["score"] if fused else x["probability"], reverse=True)
        return predictions[:top_k]

    def explain(
        self,
        text: str,
        code_indices: list[int],
        top_k: int = 5,
        batch_size: int = 16,
        with_scores: bool = False,
        method: str | None = None,
    ) -> dict[int, list]:
        """Atribución por enmascaramiento (masking perturbation) por código predicho.

        Para cada palabra del texto, la sustituye por [MASK] y mide la caída en el
        logit del código k. Las palabras que más reducen el logit son los verdaderos
        triggers del modelo para ese código concreto.

        Sólo procesa palabras de ≥ 4 caracteres para evitar ruido de stopwords.
        Los forward passes se agrupan en batches para eficiencia.

        Con ``with_scores`` devuelve pares (palabra, peso) donde el peso es la importancia
        normalizada a sumar 1 dentro de cada código. Normalizada y no absoluta porque la
        caída del logit no tiene unidades interpretables por sí sola: lo que se puede leer
        es el reparto relativo entre las palabras de un mismo código.

        ``method`` elige la estrategia (por defecto, la de ``config.json``):

        ``exhaustivo``
            Pregunta por todas las palabras. Es la referencia fiel y la más cara.
        ``divide_y_venceras``
            Enmascara grupos de palabras y descarta entero el grupo que no mueve el logit,
            partiendo por la mitad solo los que sí lo mueven.
        ``gradiente_filtrado``
            Una pasada hacia atrás ordena las palabras candidatas y solo se enmascaran las
            mejores.

        Las tres devuelven palabras medidas por enmascarado real: lo que cambia entre ellas
        es a cuántas palabras se pregunta, no cómo se mide a las que se pregunta. Por eso
        se pueden intercambiar sin cambiar la interpretación de la salida.
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

            ctx = _CtxAtribucion(
                modelo=self.model,
                base_ids=base_ids,
                base_mask=base_mask,
                mask_id=mask_id,
                word_positions=word_positions,
                code_indices=code_indices,
                baseline=baseline,
                max_len=max_len,
                batch_size=batch_size,
            )
            elegido = method or self.config.get("explain_method", EXPLAIN_POR_DEFECTO)
            if elegido not in METODOS_EXPLAIN:
                logger.warning("método de explicabilidad desconocido: %s", elegido)
                elegido = EXPLAIN_POR_DEFECTO
            # importance[wid][k] = caída en logit_k al enmascarar wid
            importance = METODOS_EXPLAIN[elegido](ctx, candidates)
            candidates = [w for w in candidates if w in importance]

            # Por cada código, ordenar palabras por importancia y devolver top_k
            results: dict[int, list[str]] = {}
            for k_pos, code_idx in enumerate(code_indices):
                scored = sorted(
                    candidates,
                    key=lambda wid: importance[wid][k_pos].item(),
                    reverse=True,
                )
                pares = [
                    (raw_words[wid].strip(_string.punctuation), importance[wid][k_pos].item())
                    for wid in scored[: top_k * 2]  # margen para filtrar residuos
                    if importance[wid][k_pos].item() > 0
                    and len(raw_words[wid].strip(_string.punctuation)) >= 4
                ]
                pares = pares[:top_k]
                if with_scores:
                    total = sum(w for _, w in pares) or 1.0
                    results[code_idx] = [(p, round(w / total, 4)) for p, w in pares]
                else:
                    results[code_idx] = [p for p, _ in pares]

            return results

        except Exception as exc:
            if _sentry:
                _sentry.capture_exception(exc)
            logger.warning("explain() falló para %d códigos: %s", len(code_indices), exc)
            return {idx: [] for idx in code_indices}

    # ------------------------------------------------------------------
    # Nota sobre la explicabilidad en modo fusión (véase main.py):
    # las dos fuentes explican cosas distintas y no se fusionan en un único
    # ranking. El diccionario aporta frases exactas que justifican el BLOQUE;
    # el modelo aporta palabras que justifican el CÓDIGO concreto dentro de ese
    # bloque. Ordenarlas juntas exigiría una escala común entre la confianza de
    # un patrón regex y la caída de un logit por enmascaramiento, y esa escala
    # no existe: inventarla sería justo el tipo de calibración sin fundamento que
    # se midió y se descartó en el Anexo F.
    # ------------------------------------------------------------------


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
