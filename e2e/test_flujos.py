"""Flujos básicos de la aplicación, recorridos por el navegador.

Cada test hace el camino completo que haría una persona. Entre los cuatro tocan las cuatro
integraciones que ninguna prueba unitaria cubre: el alta contra la base de datos, el correo por
SMTP, la sesión y el análisis de un informe por WebSocket contra el motor.
"""

import pytest
from conftest import (
    BACKEND,
    FRONTEND,
    INFORME,
    abrir_analisis,
    confirmar,
    enlace_de_confirmacion,
    iniciar_sesion,
    rellenar_registro,
    rx,
)
from playwright.sync_api import expect


class TestSalud:
    """Si esto falla, el resto de fallos no significan nada: la aplicación no está levantada."""

    def test_el_frontend_responde(self, pagina):
        respuesta = pagina.goto(f"{FRONTEND}/", wait_until="networkidle")
        assert respuesta is not None and respuesta.status == 200

    def test_el_backend_responde(self, pagina):
        assert pagina.request.get(f"{BACKEND}/api/health").status == 200


class TestRegistro:
    def test_el_alta_envia_el_correo_de_confirmacion(self, pagina, credenciales_nuevas):
        rellenar_registro(pagina, credenciales_nuevas)
        # El registro no da acceso: exige confirmar. Si esta pantalla no sale, o el alta ha
        # fallado o alguien ha quitado la verificación sin darse cuenta.
        expect(pagina.get_by_text(rx("correo|email")).first).to_be_visible(
            timeout=15_000
        )
        assert "/confirm-email?token=" in enlace_de_confirmacion(
            credenciales_nuevas["email"]
        )

    def test_confirmar_el_correo_da_acceso(self, pagina, credenciales_nuevas):
        rellenar_registro(pagina, credenciales_nuevas)
        confirmar(pagina, credenciales_nuevas["email"])
        # Tras confirmar, la aplicación entra sola y cae en la pantalla vacía de la barra lateral.
        expect(pagina.get_by_role("button", name=rx("cerrar sesión"))).to_be_visible(
            timeout=30_000
        )

    def test_el_mismo_correo_no_se_puede_registrar_dos_veces(
        self, pagina, cuenta_confirmada
    ):
        rellenar_registro(pagina, cuenta_confirmada)
        # No importa el mensaje exacto; lo que no puede pasar es que el segundo alta funcione.
        expect(pagina.locator('input[type="password"]')).to_be_visible(timeout=15_000)


class TestLogin:
    def test_credenciales_incorrectas_no_dan_acceso(self, pagina):
        iniciar_sesion(
            pagina, {"email": "noexiste@ejemplo.test", "password": "loQueSea1!"}
        )
        pagina.wait_for_timeout(3_000)
        # Sigue en el formulario: el campo de contraseña continúa en pantalla.
        expect(pagina.locator('input[type="password"]')).to_be_visible()

    def test_un_usuario_confirmado_entra(self, pagina, cuenta_confirmada):
        iniciar_sesion(pagina, cuenta_confirmada)
        expect(pagina.get_by_role("button", name=rx("cerrar sesión"))).to_be_visible(
            timeout=30_000
        )


class TestAnalisis:
    """El camino que de verdad importa: enviar un informe y recibir códigos.

    Es el único test que ejercita el WebSocket y la llamada al motor, que es donde se rompen las
    cosas cuando cambia el contrato entre servicios.
    """

    @pytest.fixture
    def sesion(self, pagina, cuenta_confirmada):
        iniciar_sesion(pagina, cuenta_confirmada)
        abrir_analisis(pagina)
        return pagina

    def enviar(self, pag):
        pag.get_by_placeholder(rx("informe")).fill(INFORME)
        pag.get_by_role("button", name=rx("analizar")).click()

    def test_enviar_un_informe_devuelve_codigos(self, sesion):
        self.enviar(sesion)
        # Un código CIE-10 en pantalla es la única señal de que la cadena entera ha funcionado.
        expect(sesion.get_by_text(rx(r"\b[A-Z]\d{2}")).first).to_be_visible(
            timeout=180_000
        )

    def test_validar_un_codigo_cambia_su_estado(self, sesion):
        self.enviar(sesion)
        validar = sesion.get_by_role("button", name=rx("validar")).first
        expect(validar).to_be_visible(timeout=180_000)
        validar.click()
        expect(sesion.get_by_text(rx("validado")).first).to_be_visible(timeout=15_000)

    def test_rechazar_un_codigo_exige_un_motivo(self, sesion):
        self.enviar(sesion)
        rechazar = sesion.get_by_role("button", name=rx("^rechazar")).first
        expect(rechazar).to_be_visible(timeout=180_000)
        rechazar.click()
        sesion.get_by_placeholder(rx("motivo")).fill("No consta en el informe")
        sesion.get_by_role("button", name=rx("confirmar rechazo")).first.click()
        expect(sesion.get_by_text(rx("rechazado")).first).to_be_visible(timeout=15_000)

    def test_borrar_la_conversacion_la_manda_a_la_papelera(self, sesion):
        self.enviar(sesion)
        # Basta con que la conversación exista; los códigos ya los comprueban los otros dos.
        conversacion = sesion.get_by_role("button", name=rx("mensaje")).first
        expect(conversacion).to_be_visible(timeout=60_000)
        # La papelera solo se dibuja al pasar el ratón sobre la conversación.
        conversacion.hover()
        sesion.get_by_title(rx("eliminar conversación")).first.click()
        # El borrado no es destructivo: la conversación pasa a la papelera y se puede restaurar.
        expect(sesion.get_by_text(rx("papelera")).first).to_be_visible(timeout=15_000)
