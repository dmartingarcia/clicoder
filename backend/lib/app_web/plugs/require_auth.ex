defmodule AppWeb.Plugs.RequireAuth do
  @moduledoc "Verifies the Bearer token from the Authorization header."

  import Plug.Conn

  def init(opts), do: opts

  def call(conn, _opts) do
    with ["Bearer " <> token] <- get_req_header(conn, "authorization"),
         {:ok, user_id} <-
           Phoenix.Token.verify(AppWeb.Endpoint, "user auth", token, max_age: 3_600) do
      # Solo el id llega a Sentry: correo e IP se filtran aparte y el id basta para localizar la cuenta.
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
