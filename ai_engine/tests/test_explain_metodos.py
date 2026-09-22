"""
Tests del registro de estrategias de atribución.

No cargan el modelo: sustituyen el encoder por uno falso con importancia conocida, que es lo
único que hace falta para comprobar que cada estrategia encuentra las palabras que importan y
que respeta el contrato común.
"""

import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).parent.parent))

from classifier import (
    EXPLAIN_POR_DEFECTO,
    METODOS_EXPLAIN,
    _CtxAtribucion,
    _explicar_divide_y_venceras,
    _explicar_exhaustivo,
    _explicar_gradiente_filtrado,
)

MASK = 999
IMPORTANTES = {2: 5.0, 7: 3.0}  # palabra → cuánto baja el logit al taparla


class EncoderFalso(torch.nn.Module):
    """Devuelve un logit que baja una cantidad fija por cada palabra importante tapada."""

    def __init__(self, n_palabras=12):
        super().__init__()
        self.n = n_palabras
        self.embeddings = torch.nn.Module()
        self.embeddings.word_embeddings = torch.nn.Embedding(1000, 4)
        self.encoder = torch.nn.Module()
        self.encoder.embeddings = self.embeddings

    def forward(self, input_ids, attention_mask=None, **_):
        base = torch.full((input_ids.shape[0], 1), 10.0)
        for fila in range(input_ids.shape[0]):
            for palabra, peso in IMPORTANTES.items():
                if input_ids[fila, palabra] == MASK:
                    base[fila, 0] -= peso
        # Término de valor nulo pero con gradiente no nulo en las posiciones importantes:
        # deja intacta la caída medida por enmascarado y a la vez da al filtro por gradiente
        # una señal que apunta a las mismas palabras, como ocurre en el modelo real.
        emb = self.embeddings.word_embeddings(input_ids)
        coef = torch.zeros(input_ids.shape[1], 1)
        for palabra, peso in IMPORTANTES.items():
            coef[palabra, 0] = peso
        gancho = (emb * coef.unsqueeze(0)).sum(dim=(1, 2), keepdim=False).unsqueeze(1)
        return base + gancho - gancho.detach()


def _contexto(n_palabras=12):
    modelo = EncoderFalso(n_palabras)
    ids = torch.arange(n_palabras).unsqueeze(0)
    msk = torch.ones_like(ids)
    wpos = {w: [w] for w in range(n_palabras)}
    with torch.no_grad():
        base = modelo(ids, msk)[0, [0]]
    return _CtxAtribucion(modelo, ids, msk, MASK, wpos, [0], base, n_palabras, 4)


def _mejores(importancia, n=2):
    return [w for w, _ in sorted(importancia.items(), key=lambda kv: -kv[1][0].item())[:n]]


# =============================================================================
# Contrato común
# =============================================================================


def test_el_registro_expone_las_tres_estrategias():
    assert set(METODOS_EXPLAIN) == {"exhaustivo", "divide_y_venceras", "gradiente_filtrado"}
    assert EXPLAIN_POR_DEFECTO in METODOS_EXPLAIN


@pytest.mark.parametrize("nombre", sorted(METODOS_EXPLAIN))
def test_toda_estrategia_encuentra_las_palabras_importantes(nombre):
    ctx = _contexto()
    imp = METODOS_EXPLAIN[nombre](ctx, list(range(12)))
    assert set(_mejores(imp)) == set(IMPORTANTES)


@pytest.mark.parametrize("nombre", sorted(METODOS_EXPLAIN))
def test_toda_estrategia_las_ordena_por_importancia(nombre):
    ctx = _contexto()
    imp = METODOS_EXPLAIN[nombre](ctx, list(range(12)))
    assert _mejores(imp, 1) == [2]  # la palabra 2 pesa 5,0 y la 7 pesa 3,0


@pytest.mark.parametrize("nombre", sorted(METODOS_EXPLAIN))
def test_ninguna_estrategia_inventa_importancia(nombre):
    """Lo que se reporta viene de una caída medida: las palabras neutras quedan a cero."""
    ctx = _contexto()
    imp = METODOS_EXPLAIN[nombre](ctx, list(range(12)))
    for palabra, valor in imp.items():
        if palabra not in IMPORTANTES:
            assert valor[0].item() == pytest.approx(0.0, abs=1e-5)


@pytest.mark.parametrize("nombre", sorted(METODOS_EXPLAIN))
def test_toda_estrategia_soporta_una_sola_candidata(nombre):
    ctx = _contexto()
    imp = METODOS_EXPLAIN[nombre](ctx, [2])
    assert imp[2][0].item() == pytest.approx(5.0, abs=1e-4)


@pytest.mark.parametrize("nombre", sorted(METODOS_EXPLAIN))
def test_toda_estrategia_soporta_lista_vacia(nombre):
    assert METODOS_EXPLAIN[nombre](_contexto(), []) == {}


# =============================================================================
# Fidelidad: las versiones rápidas se contrastan contra la referencia
# =============================================================================


def test_las_rapidas_coinciden_con_el_exhaustivo_en_el_termino_principal():
    ctx = _contexto()
    cand = list(range(12))
    ref = _mejores(_explicar_exhaustivo(ctx, cand), 1)
    for rapida in (_explicar_divide_y_venceras, _explicar_gradiente_filtrado):
        assert _mejores(rapida(_contexto(), cand), 1) == ref


def test_los_valores_reportados_son_los_mismos_que_los_del_exhaustivo():
    """Las estrategias rápidas preguntan a menos palabras, pero miden igual a las que preguntan."""
    cand = list(range(12))
    ref = _explicar_exhaustivo(_contexto(), cand)
    rapida = _explicar_gradiente_filtrado(_contexto(), cand)
    for palabra in rapida:
        assert rapida[palabra][0].item() == pytest.approx(ref[palabra][0].item(), abs=1e-4)


def test_el_gradiente_pregunta_a_menos_palabras_de_las_que_hay():
    imp = _explicar_gradiente_filtrado(_contexto(40), list(range(40)), n_verificar=8)
    assert len(imp) == 8


def test_la_poda_descarta_grupos_sin_efecto():
    """Con todas las palabras neutras salvo dos, la poda no debe recorrer el árbol entero."""
    ctx = _contexto(32)
    llamadas = []
    original = ctx.caida_al_enmascarar

    def espia(grupos):
        llamadas.append(len(grupos))
        return original(grupos)

    ctx.caida_al_enmascarar = espia
    _explicar_divide_y_venceras(ctx, list(range(32)))
    assert sum(llamadas) < 2 * 32 - 1  # menos que el árbol binario completo
