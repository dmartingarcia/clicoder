import pytest
from fastapi.testclient import TestClient

import main as main_module

RUTAS = [
    ("get", "/admin/models", None),
    ("post", "/admin/models", {"name": "inventado"}),
    ("post", "/admin/summarizer", {"model": "none"}),
]


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    with TestClient(main_module.app) as c:
        yield c


def _llamar(cliente, metodo, ruta, cuerpo, headers):
    return getattr(cliente, metodo)(ruta, headers=headers, **({"json": cuerpo} if cuerpo else {}))


@pytest.mark.parametrize("metodo,ruta,cuerpo", RUTAS)
def test_sin_token_se_rechaza(cliente, metodo, ruta, cuerpo):
    assert _llamar(cliente, metodo, ruta, cuerpo, {}).status_code == 403


@pytest.mark.parametrize("metodo,ruta,cuerpo", RUTAS)
def test_token_incorrecto_se_rechaza(cliente, metodo, ruta, cuerpo):
    r = _llamar(cliente, metodo, ruta, cuerpo, {"x-admin-token": "otro"})
    assert r.status_code == 403


@pytest.mark.parametrize("metodo,ruta,cuerpo", RUTAS)
def test_sin_token_configurado_se_rechaza_todo(cliente, monkeypatch, metodo, ruta, cuerpo):
    monkeypatch.setenv("AI_ADMIN_TOKEN", "")
    r = _llamar(cliente, metodo, ruta, cuerpo, {"x-admin-token": ""})
    assert r.status_code == 403


def test_token_correcto_se_acepta(cliente):
    r = cliente.get("/admin/models", headers={"x-admin-token": "token-de-prueba"})
    assert r.status_code == 200


def test_las_rutas_publicas_no_piden_token(cliente):
    assert cliente.get("/").status_code == 200
