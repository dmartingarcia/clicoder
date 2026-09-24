"""
Tests del registro de estrategias de atribución.

No cargan el modelo: sustituyen el encoder por uno falso con importancia conocida, que es lo
único que hace falta para comprobar que cada estrategia encuentra las palabras que importan y
que respeta el contrato común.
"""

import sys
import threading
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


def _contexto(n_palabras=12, modelo=None):
    modelo = modelo if modelo is not None else EncoderFalso(n_palabras)
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


class ModeloSinBackward(torch.nn.Module):
    """Falla al calcular el gradiente, pero funciona bajo torch.no_grad()."""

    def __init__(self):
        super().__init__()
        self.embeddings = torch.nn.Module()
        self.embeddings.word_embeddings = torch.nn.Embedding(100, 4)
        self.encoder = torch.nn.Module()
        self.encoder.embeddings = self.embeddings

    def forward(self, input_ids, attention_mask=None, **_):
        if torch.is_grad_enabled():
            raise RuntimeError("backward no soportado")
        base = torch.full((input_ids.shape[0], 1), 10.0)
        for fila in range(input_ids.shape[0]):
            for palabra, peso in IMPORTANTES.items():
                if input_ids[fila, palabra] == MASK:
                    base[fila, 0] -= peso
        return base


class ModeloSinUsarEmbeddings(torch.nn.Module):
    """El logit no depende de la capa de embeddings: el hook nunca captura nada."""

    def __init__(self):
        super().__init__()
        self.embeddings = torch.nn.Module()
        self.embeddings.word_embeddings = torch.nn.Embedding(100, 4)
        self.encoder = torch.nn.Module()
        self.encoder.embeddings = self.embeddings

    def forward(self, input_ids, attention_mask=None, **_):
        return torch.ones(input_ids.shape[0], 1, requires_grad=True) * 10.0


def test_sin_gradiente_se_degrada_al_exhaustivo():
    modelo = ModeloSinBackward()
    n = 12
    ids = torch.arange(n).unsqueeze(0)
    msk = torch.ones_like(ids)
    wpos = {w: [w] for w in range(n)}
    with torch.no_grad():
        base = modelo(ids, msk)[0, [0]]
    ctx = _CtxAtribucion(modelo, ids, msk, MASK, wpos, [0], base, n, 4)
    imp = _explicar_gradiente_filtrado(ctx, list(range(n)))
    # El resultado debe ser el mismo que el exhaustivo: solo cambió cómo se llegó a él.
    assert set(_mejores(imp)) == set(IMPORTANTES)


def test_sin_gradiente_en_los_embeddings_tambien_se_degrada():
    modelo = ModeloSinUsarEmbeddings()
    n = 6
    ids = torch.arange(n).unsqueeze(0)
    msk = torch.ones_like(ids)
    wpos = {w: [w] for w in range(n)}
    with torch.no_grad():
        base = modelo(ids, msk)[0, [0]]
    ctx = _CtxAtribucion(modelo, ids, msk, MASK, wpos, [0], base, n, 4)
    imp = _explicar_gradiente_filtrado(ctx, list(range(n)))
    # No revienta, y devuelve una medida (cero, porque el logit no depende de nada aquí).
    assert all(v[0].item() == pytest.approx(0.0, abs=1e-6) for v in imp.values())


# =============================================================================
# Fidelidad sobre un caso exigente
# =============================================================================
#
# Los casos de arriba usan 12 palabras y 2 importantes: cualquier estrategia los resuelve, de
# modo que no protegen de una regresion real (bajar los candidatos del filtro, cambiar el
# criterio de poda). Este escenario tiene 60 palabras y 8 con importancia repartida, que es la
# forma que tiene un informe de verdad, y fija un suelo de coincidencia con el exhaustivo.

IMPORTANTES_AMPLIO = {3: 9.0, 11: 7.5, 19: 6.0, 27: 4.5, 34: 3.5, 41: 2.5, 48: 1.5, 55: 0.8}


class EncoderFalsoAmplio(EncoderFalso):
    """Mismo contrato que el falso pequeño, con más palabras y más gradación."""

    def forward(self, input_ids, attention_mask=None, **_):
        base = torch.full((input_ids.shape[0], 1), 20.0)
        for fila in range(input_ids.shape[0]):
            for palabra, peso in IMPORTANTES_AMPLIO.items():
                if input_ids[fila, palabra] == MASK:
                    base[fila, 0] -= peso
        emb = self.embeddings.word_embeddings(input_ids)
        coef = torch.zeros(input_ids.shape[1], 1)
        for palabra, peso in IMPORTANTES_AMPLIO.items():
            coef[palabra, 0] = peso
        gancho = (emb * coef.unsqueeze(0)).sum(dim=(1, 2), keepdim=False).unsqueeze(1)
        return base + gancho - gancho.detach()


def _contexto_amplio(n_palabras=60):
    modelo = EncoderFalsoAmplio(n_palabras)
    ids = torch.arange(n_palabras).unsqueeze(0)
    msk = torch.ones_like(ids)
    wpos = {w: [w] for w in range(n_palabras)}
    with torch.no_grad():
        base = modelo(ids, msk)[0, [0]]
    return _CtxAtribucion(modelo, ids, msk, MASK, wpos, [0], base, n_palabras, 4)


def _solape(a, b):
    return len(set(a) & set(b)) / max(len(b), 1)


@pytest.mark.parametrize(
    "metodo,suelo",
    [(_explicar_divide_y_venceras, 0.8), (_explicar_gradiente_filtrado, 0.8)],
)
def test_las_rapidas_no_se_alejan_del_exhaustivo(metodo, suelo):
    """Suelo de coincidencia en el top-5 con la referencia, sobre 60 palabras."""
    cand = list(range(60))
    ref = _mejores(_explicar_exhaustivo(_contexto_amplio(), cand), 5)
    obtenido = _mejores(metodo(_contexto_amplio(), cand), 5)

    assert _solape(obtenido, ref) >= suelo, f"solape {_solape(obtenido, ref):.2f} < {suelo}"


@pytest.mark.parametrize("metodo", [_explicar_divide_y_venceras, _explicar_gradiente_filtrado])
def test_las_rapidas_aciertan_las_tres_mas_importantes(metodo):
    """Las tres primeras son las que ve el usuario: ahí no vale degradarse."""
    cand = list(range(60))
    ref = _mejores(_explicar_exhaustivo(_contexto_amplio(), cand), 3)
    assert _mejores(metodo(_contexto_amplio(), cand), 3) == ref


def test_ninguna_rapida_reporta_una_palabra_irrelevante_en_el_top_5():
    """Una palabra sin efecto en el top-5 sería una explicación falsa, no una imprecisa."""
    cand = list(range(60))
    for metodo in (_explicar_divide_y_venceras, _explicar_gradiente_filtrado):
        for palabra in _mejores(metodo(_contexto_amplio(), cand), 5):
            assert palabra in IMPORTANTES_AMPLIO


# =============================================================================
# Concurrencia: el hook del gradiente vive en el modelo compartido
# =============================================================================


def test_una_prediccion_concurrente_no_revienta_por_el_hook():
    """Reproduce el 500 que aparecía al analizar mientras se explicaba otro informe.

    El filtro por gradiente registra un hook sobre la capa de embeddings, que es única para
    todo el proceso. Mientras está puesto, cualquier otra pasada hacia delante lo dispara, y
    una predicción normal entra bajo `no_grad`: el `retain_grad` del hook lanzaba
    `RuntimeError: can't retain_grad on Tensor that has requires_grad=False` y el usuario
    recibía un error de un análisis que ni siquiera pedía explicación.
    """
    ctx = _contexto()
    fallos = []
    listo = threading.Event()
    parar = threading.Event()

    def predecir_sin_parar():
        listo.set()
        while not parar.is_set():
            try:
                with torch.no_grad():
                    ctx.modelo(ctx.base_ids, ctx.base_mask)
            except RuntimeError as exc:
                fallos.append(exc)
                return

    hilo = threading.Thread(target=predecir_sin_parar, daemon=True)
    hilo.start()
    listo.wait(timeout=5)
    try:
        for _ in range(20):
            _explicar_gradiente_filtrado(ctx, list(range(12)), n_verificar=4)
    finally:
        parar.set()
        hilo.join(timeout=5)

    assert fallos == [], f"una predicción concurrente falló: {fallos[0]}"


def test_dos_atribuciones_a_la_vez_no_se_pisan_el_resultado():
    """Sin serializar, el hook de una atribución captura el tensor de la pasada de la otra.

    El síntoma no sería un error sino una explicación silenciosamente equivocada, que es peor:
    el sistema justificaría un código con las palabras de otro informe.
    """
    # Un solo modelo para los cuatro hilos: es lo que hay en producción, y es la condición
    # que hace que los hooks se pisen. Con un modelo por hilo el fallo no se reproduce.
    modelo = EncoderFalso(12)
    resultados = []

    def atribuir():
        imp = _explicar_gradiente_filtrado(_contexto(modelo=modelo), list(range(12)), n_verificar=4)
        resultados.append(_mejores(imp))

    hilos = [threading.Thread(target=atribuir) for _ in range(4)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=30)

    assert len(resultados) == 4
    for mejores in resultados:
        assert set(mejores) == set(IMPORTANTES), f"atribución corrompida: {mejores}"
