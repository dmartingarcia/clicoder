defmodule AppWeb.Plugs.RequireAdmin do
  @moduledoc "Verifica que el usuario en sesión tenga is_admin=true."

  import Plug.Conn
  import Phoenix.Controller, only: [redirect: 2]

  alias App.Repo
  alias App.Accounts.User

  def init(opts), do: opts

  def call(conn, _opts) do
    user_id = get_session(conn, :admin_user_id)

    case user_id && Repo.get(User, user_id) do
      %User{is_admin: true} = user ->
        assign(conn, :current_admin, user)

      _ ->
        conn
        |> redirect(to: "/admin/login")
        |> halt()
    end
  end
end
