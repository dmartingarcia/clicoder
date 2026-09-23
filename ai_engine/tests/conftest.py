"""
Fixtures compartidas por todos los tests del motor de IA.
"""

import pytest


@pytest.fixture(autouse=True)
def sin_llamadas_a_huggingface(monkeypatch):
    """Corta la consulta de red que hace el hilo de progreso de descarga.

    Cuando un test apunta MODEL_DIR a un directorio que sí existe, el arranque
    lanza un hilo en segundo plano que pregunta a Hugging Face el tamaño del
    modelo. Sin este corte, cualquier test así intentaría red de verdad.
    """
    try:
        import huggingface_hub
        from huggingface_hub import model_info as _model_info_real  # fuerza la carga perezosa

        del _model_info_real
    except ImportError:
        return

    monkeypatch.setattr(
        huggingface_hub,
        "model_info",
        lambda name: (_ for _ in ()).throw(Exception("red deshabilitada en tests")),
    )


@pytest.fixture(autouse=True)
def summarizer_desactivado_por_defecto(monkeypatch):
    """El .env de desarrollo trae SUMMARIZER_MODEL=gemma4: sin este corte, cualquier
    test que arranque el lifespan con un MODEL_DIR real intentaría descargar el GGUF
    de verdad. Un test que quiera probar un modelo concreto lo pisa con su propio
    monkeypatch.setenv, que gana por ejecutarse después."""
    monkeypatch.setenv("SUMMARIZER_MODEL", "none")
