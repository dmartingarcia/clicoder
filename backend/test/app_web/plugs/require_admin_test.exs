defmodule AppWeb.Plugs.RequireAdminTest do
  use App.DataCase, async: true

  import Plug.Conn
  import App.Fixtures

  alias AppWeb.Plugs.RequireAdmin

  defp build_conn_with_session(session_values \\ %{}) do
    table = :ets.new(:test_session, [:set, :public])

    conn =
      Plug.Test.conn(:get, "/admin")
      |> Plug.Session.call(Plug.Session.init(store: :ets, key: "_test_key", table: table))
      |> fetch_session()

    Enum.reduce(session_values, conn, fn {k, v}, c -> put_session(c, k, v) end)
  end

  describe "RequireAdmin.init/1" do
    test "returns opts unchanged" do
      assert RequireAdmin.init([]) == []
      assert RequireAdmin.init(foo: :bar) == [foo: :bar]
    end
  end

  describe "RequireAdmin.call/2" do
    test "redirects to /admin/login and halts when there is no session" do
      conn = build_conn_with_session() |> RequireAdmin.call([])

      assert conn.halted
      assert conn.status == 302
      assert get_resp_header(conn, "location") == ["/admin/login"]
    end

    test "redirects to /admin/login when the user is not an admin" do
      user = user_fixture()

      conn =
        build_conn_with_session(%{admin_user_id: user.id})
        |> RequireAdmin.call([])

      assert conn.halted
      assert conn.status == 302
      assert get_resp_header(conn, "location") == ["/admin/login"]
    end

    test "assigns :current_admin and does not halt when the user is an admin" do
      user = user_fixture()
      admin = App.Repo.update!(Ecto.Changeset.change(user, is_admin: true))

      conn =
        build_conn_with_session(%{admin_user_id: admin.id})
        |> RequireAdmin.call([])

      refute conn.halted
      assert conn.assigns[:current_admin].id == admin.id
      assert conn.assigns[:current_admin].is_admin == true
    end

    test "redirects to /admin/login when admin_user_id does not exist in DB" do
      non_existent_id = Ecto.UUID.generate()

      conn =
        build_conn_with_session(%{admin_user_id: non_existent_id})
        |> RequireAdmin.call([])

      assert conn.halted
      assert conn.status == 302
      assert get_resp_header(conn, "location") == ["/admin/login"]
    end
  end
end
