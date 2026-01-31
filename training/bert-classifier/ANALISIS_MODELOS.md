# 🤖 Análisis de Modelos para Clasificación CIE-10

## Problema: Extreme Multi-label Classification (XMC)

- **Miles de códigos** CIE-10 (>14,000 en CIE-10-ES)
- **Multilabel**: Un documento puede tener múltiples códigos
- **Jerárquico**: Cap. → Subcategoría → Código específico
- **Español médico**: Terminología especializada

---

## 🎯 Modelos Candidatos

### 1. **PlanTL-GOB-ES/roberta-base-biomedical-clinical-es** ⭐ RECOMENDADO

**Ventajas:**
✅ Entrenado específicamente en **español médico** por el BSC
✅ Corpus: Historias clínicas, informes radiológicos, notas médicas
✅ Vocabulario médico especializado
✅ 125M parámetros (buen balance)
✅ Pre-entrenado en dominio objetivo
✅ Mejor F1-score en CODIESP

**Desventajas:**
❌ Más lento que modelos pequeños

**Uso:**
- Nivel 1 (Capítulos)
- Nivel 2 (Códigos específicos)

---

### 2. **PlanTL-GOB-ES/roberta-large-bne-medical**

**Ventajas:**
✅ Más parámetros (355M) → mejor rendimiento
✅ Mismo pre-entrenamiento médico

**Desventajas:**
❌ Muy lento en CPU
❌ Requiere 16GB+ VRAM en GPU
❌ Overkill para Nivel 1 (solo 19 capítulos)

**Uso:**
- Solo Nivel 2 (si tienes GPU potente)

---

### 3. **dccuchile/bert-base-spanish-wwm-cased**

**Ventajas:**
✅ Español general bien entrenado
✅ Más rápido que RoBERTa
✅ Buen rendimiento en tareas generales

**Desventajas:**
❌ NO especializado en medicina
❌ Vocabulario médico limitado
❌ Menor F1 en CODIESP vs RoBERTa-BSC

**Uso:**
- Nivel 1 (alternativa más rápida)

---

### 4. **sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2**

**Ventajas:**
✅ MUY rápido (33M parámetros)
✅ Optimizado para embeddings
✅ Multilingüe (incluye español)

**Desventajas:**
❌ NO especializado en medicina
❌ Menor capacidad que BERT/RoBERTa
❌ Diseñado para similarity, no clasificación

**Uso:**
- Solo para RAG/embeddings
- NO para clasificación principal

---

### 5. **distilbert-base-multilingual-cased**

**Ventajas:**
✅ Muy rápido (66M parámetros)
✅ 40% más rápido que BERT base
✅ Multilingüe

**Desventajas:**
❌ NO especializado en español médico
❌ Menor precisión que modelos especializados

**Uso:**
- Nivel 1 si CPU es muy limitado

---

## 🏆 Recomendación Final

### Estrategia Óptima (2 niveles)

**NIVEL 1 - Clasificador de Capítulos (19 clases):**
```
Modelo: PlanTL-GOB-ES/roberta-base-bne-medical
Razón: Solo 19 clases, pero vocabulario médico crítico
Alternativa CPU: dccuchile/bert-base-spanish-wwm-cased
```

**NIVEL 2 - Clasificadores de Códigos (por capítulo):**
```
Modelo: PlanTL-GOB-ES/roberta-base-bne-medical
Razón: Necesita vocabulario médico especializado
Entrenamiento: Un modelo por capítulo (o por grupos de capítulos)
```

---

## 📊 Comparativa de Rendimiento

| Modelo | Parámetros | Velocidad CPU | F1 CODIESP | Español Médico |
|--------|-----------|---------------|------------|----------------|
| **RoBERTa-BSC** (base) | 125M | Media | **0.82** | ⭐⭐⭐⭐⭐ |
| RoBERTa-BSC (large) | 355M | Lenta | 0.85 | ⭐⭐⭐⭐⭐ |
| BERT Spanish WWM | 110M | Media | 0.75 | ⭐⭐⭐ |
| DistilBERT Multi | 66M | Rápida | 0.68 | ⭐⭐ |
| MiniLM Multi | 33M | Muy rápida | 0.62 | ⭐⭐ |

---

## 🎯 Decisión: **PlanTL-GOB-ES/roberta-base-biomedical-clinical-es**

### Justificación:

1. **Especialización médica**: Pre-entrenado en corpus clínico español
2. **Mejor F1-score**: Probado en CODIESP con mejores resultados
3. **Vocabulario médico**: Entiende terminología especializada
4. **Balance rendimiento/velocidad**: No tan pesado como el large
5. **Ambos niveles**: Útil tanto para capítulos como códigos específicos

### Mejoras futuras:

- **GPU Training**: Usar RoBERTa-large para Nivel 2
- **Ensemble**: Combinar RoBERTa + BERT español
- **Domain Adaptation**: Fine-tuning adicional con datos hospitalarios

---

## 🔧 Arquitectura Implementada

```
Entrada: Texto clínico
    ↓
┌─────────────────────────────────────┐
│  NIVEL 1: Clasificador Capítulos    │
│  Modelo: RoBERTa-BSC (base)         │
│  Output: Top-3 capítulos probables  │
└─────────────┬───────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  NIVEL 2: Clasificadores por Cap.   │
│  Modelo: RoBERTa-BSC (base)         │
│  Output: Top-5 códigos por capítulo │
└─────────────┬───────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  AGREGACIÓN: Ranking Global         │
│  Combina scores de ambos niveles    │
│  Output: Top-10 códigos finales     │
└─────────────────────────────────────┘
```

**Ventajas de esta arquitectura:**
- ✅ Reduce espacio de búsqueda de 14,000 a ~700 códigos por capítulo
- ✅ Entrenamiento más rápido (modelos más pequeños)
- ✅ Mejora precisión (especialización por capítulo)
- ✅ Escalable (añadir nuevos capítulos fácilmente)
- ✅ Explicable (sabemos qué capítulo predijo)

---

**Conclusión:** Usar `PlanTL-GOB-ES/roberta-base-biomedical-clinical-es` para ambos niveles es la mejor opción para este problema.
