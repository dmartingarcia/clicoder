defmodule AppWeb.Admin.SessionController do
  use AppWeb, :controller

  alias App.Repo
  alias App.Accounts.User

  def new(conn, _params) do
    render(conn, :new)
  end

  def create(conn, %{"session" => %{"email" => email, "password" => password}}) do
    user = Repo.get_by(User, email: email, is_admin: true)

    if user && Bcrypt.verify_pass(password, user.password_hash) do
      conn
      |> put_session(:admin_user_id, user.id)
      |> redirect(to: ~p"/admin/users")
    else
      conn
      |> put_flash(:error, "Credenciales incorrectas")
      |> render(:new)
    end
  end

  def delete(conn, _params) do
    conn
    |> delete_session(:admin_user_id)
    |> redirect(to: ~p"/admin/login")
  end
end
