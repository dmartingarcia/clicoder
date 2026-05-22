defmodule AppWeb.AiController do
  use AppWeb, :controller

  def count_tokens(conn, %{"text" => text}) when is_binary(text) do
    ai_url = Application.get_env(:app, :ai_engine_url, "http://localhost:8000")

    case Req.post("#{ai_url}/count-tokens", json: %{text: text}) do
      {:ok, %{status: 200, body: body}} ->
        json(conn, body)

      {:ok, %{status: status}} ->
        conn |> put_status(status) |> json(%{error: "AI engine error"})

      {:error, _} ->
        conn |> put_status(503) |> json(%{error: "AI engine no disponible"})
    end
  end

  def count_tokens(conn, _params) do
    conn |> put_status(422) |> json(%{error: "Parámetro 'text' requerido"})
  end
end
