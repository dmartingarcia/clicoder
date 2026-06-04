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
      Req.Test.stub(App.AIEngineMock, fn conn ->
        Req.Test.transport_error(conn, :econnrefused)
      end)

      conn = post(conn, "/api/ai/count-tokens", %{"text" => "paciente con disnea"})
      assert json_response(conn, 503)["error"] =~ "no disponible"
    end

    test "returns token count when AI engine responds", %{conn: conn} do
      Req.Test.stub(App.AIEngineMock, fn conn ->
        Req.Test.json(conn, %{"token_count" => 5})
      end)

      conn = post(conn, "/api/ai/count-tokens", %{"text" => "hola mundo test"})
      assert json_response(conn, 200)["token_count"] == 5
    end
  end
end
