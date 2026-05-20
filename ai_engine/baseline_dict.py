"""
baseline_dict.py — Baseline de diccionario para clasificación CIE-10.

Para cada nota clínica busca qué códigos CIE-10 tienen su descripción (o nombre
de sustancia) mencionada en el texto, usando lematización con spaCy es_core_news_lg.
Evalúa sobre train y validación por separado para comparar directamente con los
resultados del clasificador BERT (train.py).

Los lemas de cada diccionario se cachean en disco (--cache_dir) para que
ejecuciones sucesivas no tengan que relematizar las 100k+ entradas.

Fuentes evaluadas por separado:
  diagnoses    — descripciones del diccionario diagnóstico CIE-10-MC
  procedures   — descripciones del diccionario de procedimientos CIE-10-PCS
  chemicals    — nombres de sustancias/fármacos del diccionario CIE-10-MC
  clinical     — términos clínicos reales extraídos de las anotaciones CodiESP
                 task_x, expandidos con sinónimos léxicos vía spaCy word vectors.
                 Nota: task_x incluye las etiquetas de train Y val, por lo que
                 esta fuente usa información del conjunto de evaluación → marcar
                 como "semi-supervisado" al comparar métricas.

Uso:
    python baseline_dict.py
    python baseline_dict.py --sources diagnoses clinical
    python baseline_dict.py --sources clinical --syn_similarity 0.70
    python baseline_dict.py --no_cache
"""

import argparse
import ast
import csv
import hashlib
import os
import pickle
import re
import unicodedata

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.preprocessing import MultiLabelBinarizer
from tqdm import tqdm


# ---------------------------------------------------------------------------
# Normalización y lematización
# ---------------------------------------------------------------------------

def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def build_pattern(phrase: str) -> re.Pattern:
    """Patrón con word boundaries para evitar falsos positivos de substring."""
    return re.compile(r"\b" + re.escape(phrase) + r"\b")


_nlp_trf = None   # es_dep_news_trf  — lematización contextual (transformer)
_nlp_lg  = None   # es_core_news_lg  — word vectors para synonym expansion


def _get_nlp():
    """
    Modelo transformer para lematización. Más preciso que el estadístico porque
    usa contexto completo de la frase para desambiguar lemas y POS.
    No tiene word vectors propios, por eso se carga un segundo modelo para sinónimos.
    Usa GPU automáticamente si cupy está disponible (spacy.prefer_gpu).
    """
    global _nlp_trf
    if _nlp_trf is None:
        import spacy
        spacy.prefer_gpu()
        _nlp_trf = spacy.load("es_dep_news_trf", disable=["ner"])
    return _nlp_trf


def _get_nlp_vectors():
    """
    Modelo lg para word vectors (usado solo en build_synonym_map).
    es_dep_news_trf no tiene vectores estáticos, así que cargamos
    es_core_news_lg en paralelo exclusivamente para este propósito.
    """
    global _nlp_lg
    if _nlp_lg is None:
        import spacy
        _nlp_lg = spacy.load("es_core_news_lg", disable=["parser", "ner"])
    return _nlp_lg


def normalize(text: str) -> str:
    """Minúsculas + eliminar acentos."""
    return _strip_accents(text.lower())


def _normalize_gender(lemma: str) -> str:
    """
    Normaliza el género gramatical de un lema de adjetivo al masculino singular.

    En español los adjetivos concuerdan en género con el sustantivo al que
    acompañan, por lo que "insuficiencia cardíaca" y "soplo cardíaco" producen
    lemas distintos ("cardíaca" vs "cardíaco") que fallan el matching exacto.
    Se usa el vocabulario de es_core_news_lg (que sí tiene vectores) para
    verificar que la forma masculina existe antes de sustituir.
    Solo se aplica a lemas de 4+ caracteres terminados en 'a'.
    """
    if lemma.endswith("a") and len(lemma) >= 4:
        masc = lemma[:-1] + "o"
        if not _get_nlp_vectors().vocab[masc].is_oov:
            return masc
    return lemma


def lemmatize(text: str) -> str:
    """
    Lematiza el texto con spaCy es_dep_news_trf (transformer):
    - Mejor desambiguación morfológica que el modelo estadístico.
    - Excluye espacios y puntuación.
    - Normaliza género de adjetivos al masculino (cardíaca → cardíaco).
    - Devuelve lemas en minúsculas sin acentos.
    """
    nlp = _get_nlp()
    doc = nlp(text[:100_000])
    tokens = []
    for t in doc:
        if t.is_space or t.is_punct:
            continue
        lemma = t.lemma_.lower()
        if t.pos_ == "ADJ":
            lemma = _normalize_gender(lemma)
        tokens.append(_strip_accents(lemma))
    return " ".join(tokens)


# ---------------------------------------------------------------------------
# Caché en disco
# ---------------------------------------------------------------------------

def _cache_key(*parts) -> str:
    raw = ":".join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_path(cache_dir: str, name: str, key: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{name}_{key}.pkl")


def _load_cache(path: str):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    return None


def _save_cache(path: str, data):
    with open(path, "wb") as f:
        pickle.dump(data, f)


# ---------------------------------------------------------------------------
# Expansión de sinónimos con spaCy word vectors
# ---------------------------------------------------------------------------

def find_similar_words(word: str, min_sim: float = 0.65, max_n: int = 5) -> list[str]:
    """
    Encuentra palabras similares usando los word vectors de es_core_news_lg.
    Solo devuelve palabras en minúsculas, sin números, longitud >= 4.
    """
    nlp_vec = _get_nlp_vectors()
    lex = nlp_vec.vocab[word]
    if not lex.has_vector:
        return []
    try:
        queries = np.asarray([lex.vector], dtype=np.float32)
        keys, _rows, scores = nlp_vec.vocab.vectors.most_similar(queries, n=max_n + 5)
        result = []
        for key, score in zip(keys[0], scores[0]):
            candidate = nlp_vec.vocab.strings[key].lower()
            if (candidate != word.lower()
                    and float(score) >= min_sim
                    and len(candidate) >= 4
                    and candidate.isalpha()):
                result.append(candidate)
                if len(result) >= max_n:
                    break
        return result
    except Exception:
        return []


def build_synonym_map(
    terms: set[str],
    min_sim: float = 0.65,
    max_n: int = 5,
    cache_file: str | None = None,
) -> dict[str, list[str]]:
    """
    Para cada token de contenido (NOUN, ADJ, VERB, PROPN) en los términos clínicos,
    construye un mapa word → [sinónimo1, sinónimo2, ...] usando es_core_news_lg vectors.
    """
    if cache_file:
        cached = _load_cache(cache_file)
        if cached is not None:
            print(f"  [cache] sinónimos cargados desde {cache_file}")
            return cached

    # Para POS tagging de los términos usamos el modelo transformer (más preciso)
    nlp_trf = _get_nlp()
    content_pos = {"NOUN", "ADJ", "VERB", "PROPN"}

    content_tokens: set[str] = set()
    for term in terms:
        doc = nlp_trf(term[:200])
        for tok in doc:
            if tok.pos_ in content_pos and not tok.is_stop and len(tok.text) >= 4:
                content_tokens.add(tok.lemma_.lower())

    print(f"  [synonyms] {len(content_tokens)} tokens de contenido únicos")
    syn_map: dict[str, list[str]] = {}
    for token in tqdm(sorted(content_tokens), desc="  syn expansion", unit="tok"):
        syns = find_similar_words(token, min_sim=min_sim, max_n=max_n)
        if syns:
            syn_map[token] = syns

    print(f"  [synonyms] {len(syn_map)} tokens con sinónimos")
    if cache_file:
        _save_cache(cache_file, syn_map)
        print(f"  [cache] sinónimos guardados en {cache_file}")
    return syn_map


def expand_term(raw_term: str, syn_map: dict[str, list[str]]) -> list[str]:
    """
    A partir de un término clínico lematizado, genera variantes
    sustituyendo un token a la vez por cada uno de sus sinónimos.
    Devuelve: [lema original] + [variantes con sinónimos].
    """
    lemma = lemmatize(raw_term)
    tokens = lemma.split()
    variants: list[str] = [lemma]
    for i, tok in enumerate(tokens):
        for syn in syn_map.get(tok, []):
            variant_tokens = tokens[:i] + [syn] + tokens[i+1:]
            variants.append(" ".join(variant_tokens))
    return list(dict.fromkeys(variants))  # deduplicar preservando orden


# ---------------------------------------------------------------------------
# Carga de diccionarios
# ---------------------------------------------------------------------------

def parse_labels(label_str: str) -> list[str]:
    if pd.isna(label_str) or not str(label_str).strip():
        return []
    return [c.strip().upper()[:3] for c in str(label_str).split(";") if c.strip()]


def expand_description(raw: str) -> list[str]:
    """
    Expande una descripción CIE-10 en todas sus variantes de matching:

    1. Múltiples nombres separados por '|' → un término por variante.
    2. Contenido entre paréntesis → generar:
       - Versión sin los paréntesis: "Tuberculosis de las meninges"
       - Versión con el contenido inlined: "Tuberculosis de las meninges cerebral espinal"
       - El contenido del paréntesis como término independiente (si ≥ 2 palabras):
         "alfa naftiltiourea" (nombre completo de un acrónimo)
    """
    results: list[str] = []
    for part in raw.split("|"):
        part = part.strip()
        if not part:
            continue

        # Extraer todo el contenido entre paréntesis
        paren_contents = re.findall(r"\(([^)]+)\)", part)
        # Versión sin paréntesis
        no_paren = re.sub(r"\s*\([^)]*\)", "", part).strip()
        # Versión con contenido inlined (reemplaza "(X)" por "X")
        inlined = re.sub(r"\(([^)]+)\)", r"\1", part).strip()
        inlined = re.sub(r"\s+", " ", inlined)

        results.append(no_paren)
        if inlined != no_paren:
            results.append(inlined)
        # Contenidos de paréntesis independientes (p. ej. el nombre completo de ANTU)
        for content in paren_contents:
            content = content.strip()
            if len(content.split()) >= 2:
                results.append(content)

    # Deduplicar preservando orden
    seen: set[str] = set()
    out: list[str] = []
    for r in results:
        if r and r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _build_block_patterns(
    pairs: list[tuple[str, str]],
    source: str,
    min_len: int,
    cache_dir: str | None,
    cache_key_parts: list,
) -> dict[str, list[re.Pattern]]:
    """
    Lematiza cada descripción (con caché) y compila patrones con word boundaries.
    pairs: [(block, raw_description), ...]
    """
    unique_descs = list(dict.fromkeys(desc for _, desc in pairs))
    lemma_map: dict[str, str] | None = None
    cache_file = None
    if cache_dir:
        key = _cache_key(*cache_key_parts)
        cache_file = _cache_path(cache_dir, f"lemma_{source}", key)
        cached = _load_cache(cache_file)
        if cached is not None:
            lemma_map = dict(cached)
            print(f"  [cache] lemas cargados desde {cache_file}")

    if lemma_map is None:
        print(f"  [lemma] lematizando {len(unique_descs)} descripciones únicas...")
        lemma_map = {}
        for desc in tqdm(unique_descs, desc=f"  {source}", unit="desc"):
            lemma_map[desc] = lemmatize(desc)
        if cache_file:
            _save_cache(cache_file, list(lemma_map.items()))
            print(f"  [cache] guardado en {cache_file}")

    block_patterns: dict[str, list[re.Pattern]] = {}
    for block, raw_desc in pairs:
        norm = lemma_map.get(raw_desc, "")
        if len(norm) >= min_len:
            block_patterns.setdefault(block, []).append(build_pattern(norm))
    return block_patterns


def load_diagnoses(path: str, min_len: int, cache_dir: str | None) -> dict[str, list[re.Pattern]]:
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    stat = os.stat(path)
    pairs = []
    for _, row in df.iterrows():
        block = str(row["code"]).strip().upper()[:3]
        for variant in expand_description(str(row.get("description", ""))):
            pairs.append((block, variant))
    return _build_block_patterns(pairs, "diagnoses", min_len, cache_dir,
                                  [path, stat.st_size, stat.st_mtime, min_len])


def load_procedures(path: str, min_len: int, cache_dir: str | None) -> dict[str, list[re.Pattern]]:
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    stat = os.stat(path)
    desc_cols = [c for c in ["description", "procedure", "procedure_definition",
                              "class_name", "subclass_name"] if c in df.columns]
    pairs = []
    for _, row in df.iterrows():
        block = str(row["code"]).strip().upper()[:3]
        for col in desc_cols:
            val = str(row.get(col, "")).strip()
            if val and val.lower() != "nan":
                for variant in expand_description(val):
                    pairs.append((block, variant))
    return _build_block_patterns(pairs, "procedures", min_len, cache_dir,
                                  [path, stat.st_size, stat.st_mtime, min_len])


def load_chemicals(path: str, min_len: int, cache_dir: str | None) -> dict[str, list[re.Pattern]]:
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    stat = os.stat(path)
    pairs = []
    for _, row in df.iterrows():
        raw_code = str(row.get("code1", "")).strip().upper()
        if not raw_code or raw_code in ("NAN", "-"):
            continue
        for variant in expand_description(str(row.get("description", ""))):
            pairs.append((raw_code[:3], variant))
    return _build_block_patterns(pairs, "chemicals", min_len, cache_dir,
                                  [path, stat.st_size, stat.st_mtime, min_len])


def extract_ngrams(lemma_text: str, min_n: int = 2, max_n: int = 5) -> list[str]:
    """Extrae todos los n-gramas de palabras de un texto ya lematizado."""
    tokens = lemma_text.split()
    ngrams = []
    for n in range(min_n, min(max_n + 1, len(tokens) + 1)):
        for i in range(len(tokens) - n + 1):
            ngrams.append(" ".join(tokens[i : i + n]))
    return ngrams


def load_corpus(
    train_path: str,
    min_len: int,
    cache_dir: str | None,
    min_freq: int = 2,
    min_precision: float = 0.5,
    ngram_max: int = 5,
    exclusive: bool = False,
    max_patterns: int = 0,
) -> tuple[dict[str, list[re.Pattern]], dict[str, list[str]]]:
    """
    Extrae n-gramas discriminativos de las notas de entrenamiento.

    Algoritmo:
      1. Lematizar todas las notas de train.
      2. Para cada bloque CIE-10, recoger los índices de notas que lo tienen.
      3. Para cada n-grama (2..ngram_max palabras) que aparece en esas notas:
         - freq     = nº de notas con ese bloque que contienen el n-grama.
         - total    = nº total de notas que contienen el n-grama.
         - precision = freq / total.
      4. Conservar si freq >= min_freq y precision >= min_precision.

    Si exclusive=True, cada n-grama se asigna únicamente al bloque con mayor
    precision*freq (score). Esto evita que frases genéricas contaminen múltiples
    bloques y reduce drásticamente los falsos positivos.

    Si max_patterns>0, cada bloque conserva únicamente sus top-max_patterns patrones
    ordenados por (-freq, -len). Esto limita directamente el ruido por bloque.

    Devuelve (block_patterns, top_patterns_per_block) donde top_patterns_per_block
    es un dict {block: [top-5 patrones más frecuentes]} para el reporte.
    """
    stat = os.stat(train_path)
    cache_key_parts = [train_path, stat.st_size, stat.st_mtime,
                       min_len, min_freq, min_precision, ngram_max, exclusive,
                       max_patterns]
    patterns_cache_file = None
    if cache_dir:
        key = _cache_key(*cache_key_parts)
        patterns_cache_file = _cache_path(cache_dir, "corpus", key)
        cached = _load_cache(patterns_cache_file)
        if cached is not None:
            print(f"  [cache] cargado desde {patterns_cache_file}")
            return cached

    df = pd.read_csv(train_path)
    df.columns = df.columns.str.strip()
    df.dropna(subset=["text", "labels"], inplace=True)

    # Lematizar todas las notas (caché separada, independiente de los parámetros)
    lemma_note_cache_file = None
    if cache_dir:
        lkey = _cache_key(train_path, stat.st_size, stat.st_mtime)
        lemma_note_cache_file = _cache_path(cache_dir, "corpus_lemmas", lkey)
    lemma_texts = _load_cache(lemma_note_cache_file) if lemma_note_cache_file else None
    if lemma_texts is None:
        print(f"  [lemma] lematizando {len(df)} notas de entrenamiento...")
        lemma_texts = [
            lemmatize(t) for t in tqdm(df["text"].tolist(),
                                        desc="  corpus notes", unit="nota")
        ]
        if lemma_note_cache_file:
            _save_cache(lemma_note_cache_file, lemma_texts)
    else:
        print("  [cache] lemas de notas cargados")

    labels_list = [parse_labels(lbl) for lbl in df["labels"]]

    # Índice nota → conjunto de n-gramas únicos
    note_ngrams: list[set[str]] = [
        set(extract_ngrams(lt, max_n=ngram_max)) for lt in lemma_texts
    ]

    # Recuento global: cuántas notas contienen cada n-grama
    ngram_total: dict[str, int] = {}
    for ngs in note_ngrams:
        for ng in ngs:
            ngram_total[ng] = ngram_total.get(ng, 0) + 1

    # Índice bloque → lista de índices de nota que lo tienen
    block_to_idx: dict[str, list[int]] = {}
    for i, labels in enumerate(labels_list):
        for label in labels:
            block_to_idx.setdefault(label[:3], []).append(i)

    # Recoger candidatos: {ng: {block: (freq, precision)}}
    ng_candidates: dict[str, dict[str, tuple[int, float]]] = {}

    for block, note_indices in block_to_idx.items():
        ngram_freq: dict[str, int] = {}
        for idx in note_indices:
            for ng in note_ngrams[idx]:
                ngram_freq[ng] = ngram_freq.get(ng, 0) + 1

        for ng, freq in ngram_freq.items():
            if freq < min_freq or len(ng) < min_len:
                continue
            precision = freq / ngram_total[ng]
            if precision < min_precision:
                continue
            ng_candidates.setdefault(ng, {})[block] = (freq, precision)

    # Si exclusive: cada n-grama va solo al bloque con mayor precision*freq
    if exclusive:
        exclusive_map: dict[str, str] = {}  # ng → best_block
        for ng, block_scores in ng_candidates.items():
            best = max(block_scores.items(), key=lambda x: x[1][1] * x[1][0])
            exclusive_map[ng] = best[0]

    block_patterns: dict[str, list[re.Pattern]] = {}
    block_phrases: dict[str, list[tuple[int, str]]] = {}  # block → [(freq, ng)]

    for ng, block_scores in ng_candidates.items():
        for block, (freq, _) in block_scores.items():
            if exclusive and exclusive_map[ng] != block:
                continue
            block_phrases.setdefault(block, []).append((freq, ng))

    top_patterns: dict[str, list[str]] = {}
    for block, freq_phrases in block_phrases.items():
        freq_phrases.sort(key=lambda x: (-x[0], -len(x[1])))
        if max_patterns > 0:
            freq_phrases = freq_phrases[:max_patterns]
        phrases = [ng for _, ng in freq_phrases]
        block_patterns[block] = [build_pattern(ng) for ng in phrases]
        top_patterns[block] = phrases[:5]

    result = (block_patterns, top_patterns)
    if patterns_cache_file:
        _save_cache(patterns_cache_file, result)
        print(f"  [cache] guardado en {patterns_cache_file}")
    return result


def load_clinical(
    task_x_paths: list[str],
    min_len: int,
    cache_dir: str | None,
    syn_similarity: float = 0.65,
    syn_max: int = 5,
) -> dict[str, list[re.Pattern]]:
    """
    Extrae términos clínicos reales de las anotaciones CodiESP task_x
    (DIAGNOSTICO + PROCEDIMIENTO) y los expande con sinónimos léxicos
    usando los word vectors de spaCy es_core_news_lg.

    NOTA: si task_x_paths incluye el split de validación, la fuente 'clinical'
    usa información de las etiquetas de val → semi-supervisado.
    """
    # Recoger pares (block, raw_term) de todos los task_x
    block_terms: dict[str, set[str]] = {}
    stats = []
    for path in task_x_paths:
        s = os.stat(path)
        stats.extend([path, s.st_size, s.st_mtime])
        with open(path) as f:
            for row in csv.DictReader(f):
                try:
                    anns = ast.literal_eval(row["task_x"])
                except Exception:
                    continue
                for ann in anns:
                    code = str(ann.get("code", "")).strip()
                    text = str(ann.get("text", "")).strip()
                    if not code or not text or len(text) < min_len:
                        continue
                    block = code.upper()[:3]
                    block_terms.setdefault(block, set()).add(text.lower())

    all_terms = {t for ts in block_terms.values() for t in ts}
    print(f"  {len(all_terms)} términos clínicos únicos, {len(block_terms)} bloques")

    # Construir mapa de sinónimos (con caché)
    syn_cache_file = None
    if cache_dir:
        syn_key = _cache_key(*stats, syn_similarity, syn_max)
        syn_cache_file = _cache_path(cache_dir, "synonyms_clinical", syn_key)
    syn_map = build_synonym_map(all_terms, min_sim=syn_similarity,
                                max_n=syn_max, cache_file=syn_cache_file)

    # Lematizar términos + expandir con sinónimos (con caché)
    patterns_cache_file = None
    if cache_dir:
        pat_key = _cache_key(*stats, syn_similarity, syn_max, min_len)
        patterns_cache_file = _cache_path(cache_dir, "patterns_clinical", pat_key)
    cached_patterns = _load_cache(patterns_cache_file) if patterns_cache_file else None
    if cached_patterns is not None:
        print(f"  [cache] patrones cargados desde {patterns_cache_file}")
        return cached_patterns

    # Generar patrones expandidos
    block_patterns: dict[str, list[re.Pattern]] = {}
    all_blocks_terms = list(block_terms.items())
    for block, terms in tqdm(all_blocks_terms, desc="  clinical patterns", unit="block"):
        patterns = []
        seen_phrases: set[str] = set()
        for term in terms:
            for phrase in expand_term(term, syn_map):
                if phrase not in seen_phrases and len(phrase) >= min_len:
                    seen_phrases.add(phrase)
                    patterns.append(build_pattern(phrase))
        if patterns:
            block_patterns[block] = patterns

    if patterns_cache_file:
        _save_cache(patterns_cache_file, block_patterns)
        print(f"  [cache] patrones guardados en {patterns_cache_file}")
    return block_patterns


# ---------------------------------------------------------------------------
# Predicción
# ---------------------------------------------------------------------------


def predict(
    texts: list[str],
    block_patterns: dict[str, list[re.Pattern]],
    split: str,
    mlb_classes: set[str],
) -> tuple[list[list[str]], int]:
    """
    Predice bloques para cada texto.
    Devuelve (predicciones, n_ignorados) donde n_ignorados son bloques
    predichos pero no presentes en el MLBinarizer (fuera del universo CodiESP).
    """
    results = []
    n_ignored = 0
    for text in tqdm(texts, desc=f"  predicting {split}", unit="note"):
        norm_text = lemmatize(text)
        predicted = []
        for block, patterns in block_patterns.items():
            if any(p.search(norm_text) for p in patterns):
                if block in mlb_classes:
                    predicted.append(block)
                else:
                    n_ignored += 1
        results.append(predicted)
    return results, n_ignored


# ---------------------------------------------------------------------------
# Métricas — formato idéntico a train.py
# ---------------------------------------------------------------------------

def print_metrics(Y_true, Y_pred, split: str, source: str, n_ignored: int = 0):
    p_micro  = precision_score(Y_true, Y_pred, average="micro", zero_division=0)
    r_micro  = recall_score   (Y_true, Y_pred, average="micro", zero_division=0)
    f1_micro = f1_score       (Y_true, Y_pred, average="micro", zero_division=0)
    p_macro  = precision_score(Y_true, Y_pred, average="macro", zero_division=0)
    r_macro  = recall_score   (Y_true, Y_pred, average="macro", zero_division=0)
    f1_macro = f1_score       (Y_true, Y_pred, average="macro", zero_division=0)
    n_pred   = int(Y_pred.sum())
    n_true   = int(Y_true.sum())

    print(f"\n[result] dict/{source}  split={split}")
    print(f"  micro — P={p_micro:.3f}  R={r_micro:.3f}  F1={f1_micro:.3f}")
    print(f"  macro — P={p_macro:.3f}  R={r_macro:.3f}  F1={f1_macro:.3f}")
    print(f"  predicciones: {n_pred}  verdaderos: {n_true}", end="")
    if n_ignored:
        print(f"  ignorados (fuera CodiESP): {n_ignored}", end="")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train_file",
        default="/data/codiesp_csvs/codiesp_D_source_train.csv")
    parser.add_argument("--val_file",
        default="/data/codiesp_csvs/codiesp_D_source_validation.csv")
    parser.add_argument("--diagnoses_file",
        default="/data/cie10-csvs/cie10-es-diagnoses.csv")
    parser.add_argument("--procedures_file",
        default="/data/cie10-csvs/cie10-es-procedures.csv")
    parser.add_argument("--chemicals_file",
        default="/data/cie10-csvs/cie10-es-chemicals.csv")
    parser.add_argument("--task_x_train",
        default="/data/codiesp_csvs/codiesp_X_source_train.csv")
    parser.add_argument("--task_x_val",
        default="/data/codiesp_csvs/codiesp_X_source_validation.csv",
        help="Anotaciones de val (usa etiquetas de val → semi-supervisado)")
    parser.add_argument("--sources", nargs="+",
        choices=["diagnoses", "procedures", "chemicals", "clinical", "corpus", "combined"],
        default=["diagnoses", "procedures", "chemicals", "clinical", "corpus", "combined"])
    parser.add_argument("--only_combined", action="store_true",
        help="Carga todas las fuentes en silencio y solo evalúa combined")
    parser.add_argument("--min_phrase_len", type=int, default=5)
    parser.add_argument("--syn_similarity", type=float, default=0.65,
        help="Similitud mínima para expansión de sinónimos (0–1, default 0.65)")
    parser.add_argument("--syn_max", type=int, default=5,
        help="Número máximo de sinónimos por token (default 5)")
    parser.add_argument("--corpus_min_freq", type=int, default=2,
        help="Frecuencia mínima de un n-grama en notas con su bloque (default 2)")
    parser.add_argument("--corpus_min_precision", type=float, default=0.5,
        help="Fracción mínima de apariciones del n-grama en notas de su bloque (default 0.5)")
    parser.add_argument("--corpus_ngram_max", type=int, default=5,
        help="Máximo número de palabras por n-grama (default 5)")
    parser.add_argument("--corpus_exclusive", action="store_true",
        help="Asigna cada n-grama solo al bloque con mayor precision (reduce falsos positivos)")
    parser.add_argument("--corpus_max_patterns", type=int, default=0,
        help="Límite de patrones por bloque, ordenados por frecuencia (0=sin límite)")
    parser.add_argument("--corpus_selective", action="store_true",
        help="En combined, corpus solo cubre bloques que clinical no tiene (relleno del recall faltante)")
    parser.add_argument("--report_file",
        default="/app/model/baseline_report.csv",
        help="CSV con tabla bloque→top patrones por fuente (default: /app/model/baseline_report.csv)")
    parser.add_argument("--cache_dir", default="/app/model/baseline_cache")
    parser.add_argument("--no_cache", action="store_true")
    parser.add_argument("--save_dict",
        help="Guarda los patrones combined como JSON en esta ruta (para usar en API)")
    args = parser.parse_args()

    cache_dir = None if args.no_cache else args.cache_dir

    # Cargar splits
    splits = {}
    for name, path in [("train", args.train_file), ("val", args.val_file)]:
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip()
        df.dropna(subset=["text", "labels"], inplace=True)
        splits[name] = df
        print(f"[data] {name}={len(df)}")

    # MLBinarizer sobre la unión de bloques de ambos splits
    all_labels = [parse_labels(lbl) for df in splits.values() for lbl in df["labels"]]
    all_blocks = sorted({b for lbls in all_labels for b in lbls})
    mlb_classes = set(all_blocks)
    mlb = MultiLabelBinarizer()
    mlb.fit([all_blocks])
    print(f"[data] {len(all_blocks)} bloques únicos (union train+val)")

    print("[nlp] Cargando es_dep_news_trf (lematización)...")
    _get_nlp()
    print("[nlp] Cargando es_core_news_lg (word vectors)...")
    _get_nlp_vectors()
    print("[nlp] Modelos cargados")

    source_loaders = {
        "diagnoses":  lambda: (load_diagnoses(args.diagnoses_file, args.min_phrase_len, cache_dir), {}),
        "procedures": lambda: (load_procedures(args.procedures_file, args.min_phrase_len, cache_dir), {}),
        "chemicals":  lambda: (load_chemicals(args.chemicals_file, args.min_phrase_len, cache_dir), {}),
        "clinical":   lambda: (load_clinical(
            task_x_paths=[p for p in [args.task_x_train, args.task_x_val]
                          if p and os.path.exists(p)],
            min_len=args.min_phrase_len,
            cache_dir=cache_dir,
            syn_similarity=args.syn_similarity,
            syn_max=args.syn_max,
        ), {}),
        "corpus": lambda: load_corpus(
            args.train_file,
            args.min_phrase_len,
            cache_dir,
            min_freq=args.corpus_min_freq,
            min_precision=args.corpus_min_precision,
            ngram_max=args.corpus_ngram_max,
            exclusive=args.corpus_exclusive,
            max_patterns=args.corpus_max_patterns,
        ),
    }

    # Acumular top patrones para el reporte final, y patrones por fuente para combined
    report_rows: list[dict] = []
    all_loaded: dict[str, dict[str, list[re.Pattern]]] = {}  # source → block_patterns

    all_individual = ["diagnoses", "procedures", "chemicals", "clinical", "corpus"]
    if args.only_combined:
        # Respetar --sources para elegir qué cargar; si no se especifica ninguna
        # fuente individual en --sources, cargar todas por defecto.
        requested = [s for s in args.sources if s != "combined"]
        individual_sources = requested if requested else all_individual
        run_combined = True
    else:
        individual_sources = [s for s in args.sources if s != "combined"]
        run_combined = "combined" in args.sources

    eval_individual = not args.only_combined

    for source in individual_sources:
        if source == "clinical":
            print("\n[clinical] task_x train+val")
            print("  NOTA: usa etiquetas de val → resultados semi-supervisados")
        elif source == "corpus":
            print(f"\n[corpus] n-gramas discriminativos de {args.train_file}")
            print(f"  min_freq={args.corpus_min_freq}  "
                  f"min_precision={args.corpus_min_precision}  "
                  f"ngram_max={args.corpus_ngram_max}")
        else:
            path = getattr(args, f"{source}_file")
            print(f"\n[{source}] {path}")

        try:
            block_patterns, top_patterns = source_loaders[source]()
        except FileNotFoundError as e:
            print(f"  SKIP — archivo no encontrado: {e}")
            continue

        n_blocks  = len(block_patterns)
        n_phrases = sum(len(v) for v in block_patterns.values())
        print(f"  {n_blocks} bloques, {n_phrases} patrones")

        all_loaded[source] = block_patterns

        # Acumular para reporte
        for block, phrases in top_patterns.items():
            report_rows.append({
                "fuente": source,
                "bloque": block,
                "n_patrones": len(block_patterns.get(block, [])),
                "top_patrones": " | ".join(phrases),
            })

        if not eval_individual:
            continue

        for split_name, df in splits.items():
            labels = [parse_labels(lbl) for lbl in df["labels"]]
            Y_true = mlb.transform(labels)
            preds, n_ignored = predict(df["text"].tolist(), block_patterns,
                                       split_name, mlb_classes)
            Y_pred = mlb.transform(preds)
            print_metrics(Y_true, Y_pred, split=split_name, source=source,
                          n_ignored=n_ignored)

    # Fuente combinada: unión de todos los patrones cargados
    if run_combined and all_loaded:
        # Corpus selectivo: si está activo, los patrones de corpus solo se añaden
        # para bloques que clinical NO cubre. Así corpus actúa de relleno del 14%
        # de recall que clinical no alcanza sin contaminar los bloques que clinical
        # ya resuelve bien.
        corpus_selective = args.corpus_selective and "corpus" in all_loaded and "clinical" in all_loaded
        clinical_blocks = set(all_loaded["clinical"].keys()) if corpus_selective else set()
        if corpus_selective:
            n_filtered = sum(1 for b in all_loaded["corpus"] if b in clinical_blocks)
            print(f"\n[combined] corpus selectivo — filtrando {n_filtered} bloques ya cubiertos por clinical")

        print(f"\n[combined] unión de {list(all_loaded.keys())}")
        combined: dict[str, list[re.Pattern]] = {}
        for src, bp in all_loaded.items():
            for block, patterns in bp.items():
                if corpus_selective and src == "corpus" and block in clinical_blocks:
                    continue
                combined.setdefault(block, []).extend(patterns)
        n_blocks  = len(combined)
        n_phrases = sum(len(v) for v in combined.values())
        print(f"  {n_blocks} bloques, {n_phrases} patrones")
        for split_name, df in splits.items():
            labels = [parse_labels(lbl) for lbl in df["labels"]]
            Y_true = mlb.transform(labels)
            preds, n_ignored = predict(df["text"].tolist(), combined,
                                       split_name, mlb_classes)
            Y_pred = mlb.transform(preds)
            print_metrics(Y_true, Y_pred, split=split_name, source="combined",
                          n_ignored=n_ignored)

    # Guardar patrones combined como JSON para uso en API
    if args.save_dict and run_combined and all_loaded:
        import json

        def _pat_to_phrase(pat: re.Pattern) -> str:
            """Invierte build_pattern: extrae la frase original de la regex."""
            inner = pat.pattern[2:-2]  # quita \b de inicio y fin
            return re.sub(r"\\(.)", r"\1", inner)

        phrases_map = {
            block: [_pat_to_phrase(p) for p in patterns]
            for block, patterns in combined.items()
        }
        os.makedirs(os.path.dirname(os.path.abspath(args.save_dict)), exist_ok=True)
        with open(args.save_dict, "w") as f:
            json.dump(phrases_map, f, ensure_ascii=False, indent=2)
        n_phrases = sum(len(v) for v in phrases_map.values())
        print(f"\n[save_dict] {len(phrases_map)} bloques, {n_phrases} frases → {args.save_dict}")

    # Escribir reporte CSV
    if report_rows and args.report_file:
        os.makedirs(os.path.dirname(args.report_file), exist_ok=True)
        report_df = pd.DataFrame(report_rows)
        report_df.sort_values(["fuente", "bloque"], inplace=True)
        report_df.to_csv(args.report_file, index=False)
        print(f"\n[report] {len(report_rows)} filas escritas en {args.report_file}")

    print()


class DictClassifier:
    """
    Clasificador de diccionario listo para usar en API.

    Carga los patrones guardados con --save_dict y expone predict(text).
    La confianza es 1.0 para cualquier match (sistema determinista); se incluyen
    los términos que dispararon cada código para trazabilidad.
    """

    def __init__(self, patterns_path: str):
        import json
        with open(patterns_path) as f:
            data: dict[str, list[str]] = json.load(f)
        # Recompilar las frases como patrones regex con word boundaries
        self._phrases: dict[str, list[str]] = data
        self._patterns: dict[str, list[re.Pattern]] = {
            block: [build_pattern(p) for p in phrases]
            for block, phrases in data.items()
        }

    def predict(self, text: str) -> list[dict]:
        """
        Devuelve lista de {code, confidence, matched_terms} ordenada por código.

        confidence=1.0 para todos los matches (regla determinista).
        matched_terms lista los primeros 3 términos que dispararon el código,
        útil para explicar al usuario por qué se predijo ese bloque.
        """
        ltext = lemmatize(text)
        results = []
        for block, patterns in self._patterns.items():
            matched = [
                self._phrases[block][i]
                for i, pat in enumerate(patterns)
                if pat.search(ltext)
            ]
            if matched:
                results.append({
                    "code":          block,
                    "confidence":    1.0,
                    "matched_terms": matched[:3],
                })
        results.sort(key=lambda x: x["code"])
        return results


if __name__ == "__main__":
    main()
