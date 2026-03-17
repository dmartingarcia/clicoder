defmodule AppWeb.Plugs.RequireAuth do
  @moduledoc "Verifies the Bearer token from the Authorization header."

  import Plug.Conn

  def init(opts), do: opts

  def call(conn, _opts) do
    with ["Bearer " <> token] <- get_req_header(conn, "authorization"),
         {:ok, user_id} <- Phoenix.Token.verify(AppWeb.Endpoint, "user auth", token, max_age: 86_400 * 30) do
      assign(conn, :current_user_id, user_id)
    else
      _ ->
        conn
        |> send_resp(401, ~s({"error":"Unauthorized"}))
        |> halt()
    end
  end
end
