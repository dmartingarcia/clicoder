defmodule AppWeb.SentryFilterTest do
  @moduledoc """
  Lo que sale hacia Sentry no puede llevar datos personales ni el informe clínico.

  Un aviso de error viaja a un tercero, de modo que todo lo que se adjunte sale del sistema.
  El informe es categoría especial del artículo 9 del RGPD y la dirección IP es dato personal
  del artículo 4. Lo que sí debe viajar son identificadores: sin ellos el error no se puede
  investigar, y con ellos basta, porque la conversación y el usuario se localizan en la base
  de datos local. Estos tests fijan esa frontera: el fallo sería invisible, porque el sistema
  seguiría funcionando igual mientras filtra.
  """
  use ExUnit.Case, async: true

  alias AppWeb.SentryFilter

  defp evento(attrs) do
    struct(Sentry.Event, attrs) |> SentryFilter.filter_event()
  end

  describe "el informe clínico no sale" do
    test "el cuerpo de la petición se filtra" do
      ev =
        evento(
          request: %{
            body_params: %{"report_text" => "Paciente con disnea", "content" => "texto"},
            headers: [],
            env: %{}
          }
        )

      assert ev.request.body_params == %{
               "report_text" => "[FILTERED]",
               "content" => "[FILTERED]"
             }
    end

    test "también dentro de un mapa anidado" do
      ev = evento(request: %{body_params: %{"a" => %{"content" => "x"}}, headers: [], env: %{}})
      assert ev.request.body_params == %{"a" => %{"content" => "[FILTERED]"}}
    end
  end

  describe "los datos personales no salen" do
    test "la IP del cliente se elimina" do
      ev =
        evento(
          request: %{
            body_params: %{},
            headers: [{"x-forwarded-for", "8.8.8.8"}, {"accept", "json"}],
            env: %{"REMOTE_ADDR" => "8.8.8.8", "REQUEST_METHOD" => "POST"}
          }
        )

      refute Map.has_key?(ev.request.env, "REMOTE_ADDR")
      assert ev.request.env["REQUEST_METHOD"] == "POST"
      assert {"x-forwarded-for", "[FILTERED]"} in ev.request.headers
      assert {"accept", "json"} in ev.request.headers
    end

    test "el token de confirmación en la ruta no sale" do
      ev =
        evento(
          request: %{
            url: "https://x.test/auth/confirm/abc123",
            body_params: %{},
            headers: [],
            env: %{"PATH_INFO" => "/auth/confirm/abc123"}
          }
        )

      assert ev.request.url == "https://x.test/auth/confirm/[FILTERED]"
      assert ev.request.env["PATH_INFO"] == "/auth/confirm/[FILTERED]"
    end

    test "la cadena de consulta se filtra: lleva el token de confirmación" do
      ev = evento(request: %{body_params: %{}, headers: [], env: %{}, query_string: "token=abc"})
      assert ev.request.query_string == "[FILTERED]"
    end

    test "del usuario solo viaja el identificador" do
      ev = evento(user: %{id: "u-1", email: "ana@ejemplo.test", ip_address: "8.8.8.8"})
      assert ev.user == %{id: "u-1"}
    end
  end

  test "un evento sin petición ni usuario no rompe el filtro" do
    assert %Sentry.Event{} = evento(request: nil, user: nil)
  end
end
