defmodule AppWeb.Plugs.RequireAuth do
  @moduledoc "Verifies the Bearer token from the Authorization header."

  import Plug.Conn

  def init(opts), do: opts

  def call(conn, _opts) do
    with ["Bearer " <> token] <- get_req_header(conn, "authorization"),
         {:ok, user_id} <-
           Phoenix.Token.verify(AppWeb.Endpoint, "user auth", token, max_age: 3_600) do
      # Un error en una peticion HTTP llegaba a Sentry sin saber a quien le habia pasado, de modo
      # que no se podia investigar. Solo el identificador: el correo y la IP se filtran aparte
      # porque salen del sistema, y con el id la cuenta se localiza en la base de datos local.
      if Code.ensure_loaded?(Sentry.Context) do
        Sentry.Context.set_user_context(%{id: user_id})
      end

      assign(conn, :current_user_id, user_id)
    else
      _ ->
        conn
        |> send_resp(401, ~s({"error":"Unauthorized"}))
        |> halt()
    end
  end
end
