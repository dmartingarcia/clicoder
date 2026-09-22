defmodule AppWeb.Admin.SessionControllerTest do
  @moduledoc """
  Autenticación del backoffice. Se prueba con detalle porque es la única barrera entre un
  visitante y los datos de todas las conversaciones: aquí un fallo no degrada el servicio,
  lo expone.
  """
  use AppWeb.ConnCase

  alias App.Repo

  defp admin_fixture do
    App.Fixtures.user_fixture(%{"password" => "adminpassword123"})
    |> Ecto.Changeset.change(is_admin: true)
    |> Repo.update!()
  end

  describe "GET /admin/login" do
    test "muestra el formulario", %{conn: conn} do
      conn = get(conn, ~p"/admin/login")
      assert html_response(conn, 200) =~ "Login"
    end
  end

  describe "POST /admin/login" do
    test "con credenciales correctas crea la sesión y redirige", %{conn: conn} do
      admin = admin_fixture()

      conn =
        post(conn, ~p"/admin/login", %{
          "session" => %{"email" => admin.email, "password" => "adminpassword123"}
        })

      assert redirected_to(conn) == ~p"/admin/users"
      assert get_session(conn, :admin_user_id) == admin.id
    end

    test "con contraseña incorrecta no crea sesión", %{conn: conn} do
      admin = admin_fixture()

      conn =
        post(conn, ~p"/admin/login", %{
          "session" => %{"email" => admin.email, "password" => "equivocada"}
        })

      assert html_response(conn, 200) =~ "Credenciales incorrectas"
      refute get_session(conn, :admin_user_id)
    end

    test "un usuario que existe pero no es administrador no entra", %{conn: conn} do
      normal = App.Fixtures.user_fixture(%{"password" => "usuariopassword123"})

      conn =
        post(conn, ~p"/admin/login", %{
          "session" => %{"email" => normal.email, "password" => "usuariopassword123"}
        })

      assert html_response(conn, 200) =~ "Credenciales incorrectas"
      refute get_session(conn, :admin_user_id)
    end

    test "con un correo inexistente no revela que no existe", %{conn: conn} do
      conn =
        post(conn, ~p"/admin/login", %{
          "session" => %{"email" => "nadie@example.com", "password" => "loquesea"}
        })

      # El mismo mensaje que con contraseña incorrecta: distinguirlos permitiría
      # enumerar qué correos tienen cuenta de administrador.
      assert html_response(conn, 200) =~ "Credenciales incorrectas"
      refute get_session(conn, :admin_user_id)
    end
  end

  describe "DELETE /admin/logout" do
    test "cierra la sesión y redirige al login", %{conn: conn} do
      admin = admin_fixture()
      conn = Plug.Test.init_test_session(conn, admin_user_id: admin.id)

      conn = delete(conn, ~p"/admin/logout")

      assert redirected_to(conn) == ~p"/admin/login"
      refute get_session(conn, :admin_user_id)
    end
  end

  describe "salud del servicio" do
    test "responde sin autenticación", %{conn: conn} do
      conn = get(conn, ~p"/api/health")
      assert response(conn, 200)
    end
  end
end
