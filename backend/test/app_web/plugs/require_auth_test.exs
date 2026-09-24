defmodule AppWeb.Plugs.RequireAuthTest do
  use App.DataCase, async: true

  import Plug.Conn
  import App.Fixtures

  alias AppWeb.Plugs.RequireAuth

  describe "RequireAuth.init/1" do
    test "returns opts unchanged" do
      assert RequireAuth.init([]) == []
      assert RequireAuth.init(foo: :bar) == [foo: :bar]
    end
  end

  describe "RequireAuth.call/2" do
    test "assigns :current_user_id and does not halt with a valid Bearer token" do
      user = user_fixture()

      conn =
        Plug.Test.conn(:get, "/api/conversations")
        |> put_req_header("authorization", "Bearer #{generate_token(user)}")
        |> RequireAuth.call([])

      refute conn.halted
      assert conn.assigns[:current_user_id] == user.id
    end

    test "sets the Sentry user context to just the user id" do
      user = user_fixture()

      Plug.Test.conn(:get, "/api/conversations")
      |> put_req_header("authorization", "Bearer #{generate_token(user)}")
      |> RequireAuth.call([])

      # El correo y la IP se filtran aparte (AppWeb.SentryFilter) porque son datos
      # personales; el identificador es lo único que debe llegar a un tercero.
      assert Sentry.Context.get_all().user == %{id: user.id}
    end

    test "returns 401 and halts without an authorization header" do
      conn =
        Plug.Test.conn(:get, "/api/conversations")
        |> RequireAuth.call([])

      assert conn.halted
      assert conn.status == 401
    end

    test "returns 401 and halts with a malformed authorization header" do
      conn =
        Plug.Test.conn(:get, "/api/conversations")
        |> put_req_header("authorization", "not-a-bearer-token")
        |> RequireAuth.call([])

      assert conn.halted
      assert conn.status == 401
    end

    test "returns 401 and halts with an invalid token" do
      conn =
        Plug.Test.conn(:get, "/api/conversations")
        |> put_req_header("authorization", "Bearer garbage")
        |> RequireAuth.call([])

      assert conn.halted
      assert conn.status == 401
    end
  end
end
