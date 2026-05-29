defmodule AppWeb.AiControllerTest do
  use AppWeb.ConnCase, async: true

  describe "POST /api/ai/count-tokens" do
    test "returns 422 when text param is missing", %{conn: conn} do
      conn = post(conn, "/api/ai/count-tokens", %{})
      assert json_response(conn, 422)["error"] =~ "requerido"
    end

    test "returns 422 when text is not a string", %{conn: conn} do
      conn = post(conn, "/api/ai/count-tokens", %{"text" => 123})
      assert json_response(conn, 422)["error"] =~ "requerido"
    end

    test "returns 503 when AI engine is unreachable", %{conn: conn} do
      # The AI engine is not running in tests; connection is refused → 503.
      conn = post(conn, "/api/ai/count-tokens", %{"text" => "paciente con disnea"})
      assert json_response(conn, 503)["error"] =~ "no disponible"
    end
  end
end
