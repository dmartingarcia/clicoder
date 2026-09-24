"""Configuración compartida de los tests de extremo a extremo.

Se ejecutan contra la aplicación levantada de verdad: frontend, backend, base de datos, motor y
servidor de correo. Cubren lo que ninguna otra capa de pruebas alcanza, que es que esas piezas
hablan entre sí por HTTP, WebSocket y SMTP. No sustituyen a los tests unitarios.
"""

import os
import re
import time
import uuid

import pytest
import requests
from playwright.sync_api import Page, sync_playwright

FRONTEND = os.environ.get("E2E_FRONTEND_URL", "http://localhost:3000")
BACKEND = os.environ.get("E2E_BACKEND_URL", "http://localhost:4000")
MAILPIT = os.environ.get("E2E_MAILPIT_URL", "http://localhost:8025")


def rx(patron: str) -> "re.Pattern[str]":
    """Patrón sin distinguir mayúsculas: los textos vienen de las traducciones."""
    return re.compile(patron, re.IGNORECASE)


INFORME = (
    "Paciente varón de 68 años, fumador de 20 cigarrillos al día, que acude por disnea "
    "de esfuerzo progresiva y tos productiva de tres semanas de evolución. Antecedentes de "
    "hipertensión arterial y diabetes mellitus tipo 2 en tratamiento. A la exploración, "
    "crepitantes bibasales y saturación del 91 % basal."
)


@pytest.fixture(scope="session")
def navegador():
    with sync_playwright() as p:
        nav = p.chromium.launch()
        yield nav
        nav.close()


def _nueva_pagina(navegador) -> Page:
    contexto = navegador.new_context(viewport={"width": 1280, "height": 900})
    pag = contexto.new_page()
    # Un fallo de red o una excepción de JavaScript suelen ser la causa real de que un test caiga
    # por "no encuentro el elemento". Verlos en el informe ahorra media hora de bisección.
    pag.on("pageerror", lambda e: print(f"[js] {e}"))
    pag.on("requestfailed", lambda r: print(f"[red] {r.method} {r.url}"))
    return pag


@pytest.fixture
def pagina(navegador):
    pag = _nueva_pagina(navegador)
    yield pag
    pag.context.close()


@pytest.fixture
def credenciales_nuevas() -> dict:
    sufijo = uuid.uuid4().hex[:10]
    return {
        "first_name": "Ana",
        "last_name": "Pruebas",
        "username": f"ana_{sufijo}",
        "email": f"e2e_{sufijo}@ejemplo.test",
        "password": "PruebaSegura1!",
    }


def rellenar_registro(pag: Page, datos: dict) -> None:
    """Abre la pestaña de registro y envía el formulario."""
    pag.goto(f"{FRONTEND}/", wait_until="networkidle")
    pag.get_by_role("button", name=rx(r"^(registr|sign up|crear)")).first.click()
    pag.get_by_placeholder("Juan").fill(datos["first_name"])
    pag.get_by_placeholder("García López").fill(datos["last_name"])
    pag.get_by_placeholder("dr_garcia").fill(datos["username"])
    pag.locator('input[type="email"]').fill(datos["email"])
    pag.locator('input[type="password"]').fill(datos["password"])
    pag.locator('button[type="submit"]').click()


def enlace_de_confirmacion(email: str, espera: float = 20.0) -> str:
    """Devuelve el enlace de confirmación del último correo enviado a `email`.

    El correo pasa por Mailpit, el mismo servidor SMTP que usa el entorno de desarrollo, así que
    el test comprueba el envío real y no una simulación.
    """
    limite = time.monotonic() + espera
    while time.monotonic() < limite:
        busqueda = requests.get(
            f"{MAILPIT}/api/v1/search", params={"query": f"to:{email}"}, timeout=5
        ).json()
        if busqueda.get("messages"):
            ident = busqueda["messages"][0]["ID"]
            cuerpo = requests.get(f"{MAILPIT}/api/v1/message/{ident}", timeout=5).json()
            enlace = re.search(
                r"https?://\S+/confirm-email\?token=[\w.-]+", cuerpo.get("Text", "")
            )
            if enlace:
                return enlace.group(0)
        time.sleep(0.5)
    raise AssertionError(
        f"No llegó el correo de confirmación a {email} en {espera:.0f} s"
    )


def confirmar(pag: Page, email: str) -> None:
    """Sigue el enlace del correo. Al confirmar, la aplicación deja la sesión ya iniciada."""
    destino = enlace_de_confirmacion(email)
    # El correo apunta al dominio configurado en el backend, que no tiene por qué ser la URL por
    # la que el test llega al frontend (contenedor frente a host).
    pag.goto(re.sub(r"^https?://[^/]+", FRONTEND, destino), wait_until="networkidle")


@pytest.fixture
def cuenta_confirmada(navegador, credenciales_nuevas) -> dict:
    """Usuario dado de alta y con el correo ya confirmado, en un contexto que luego se descarta."""
    pag = _nueva_pagina(navegador)
    try:
        rellenar_registro(pag, credenciales_nuevas)
        confirmar(pag, credenciales_nuevas["email"])
    finally:
        pag.context.close()
    return credenciales_nuevas


def iniciar_sesion(pag: Page, datos: dict) -> None:
    pag.goto(f"{FRONTEND}/", wait_until="networkidle")
    pag.locator('input[type="email"]').fill(datos["email"])
    pag.locator('input[type="password"]').fill(datos["password"])
    pag.locator('button[type="submit"]').click()


def abrir_analisis(pag: Page) -> None:
    """Entra en la conversación de trabajo: al iniciar sesión se cae en la pantalla vacía."""
    boton = pag.get_by_role("button", name=rx("nuevo análisis")).first
    boton.wait_for(state="visible", timeout=30_000)
    boton.click()
    pag.get_by_placeholder(rx("informe")).wait_for(state="visible", timeout=30_000)
