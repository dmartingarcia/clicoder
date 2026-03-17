defmodule AppWeb.TranslationController do
  use AppWeb, :controller

  @supported_locales ~w(es en)
  @default_locale "es"

  def show(conn, %{"locale" => locale}) do
    locale = if locale in @supported_locales, do: locale, else: @default_locale
    path = Application.app_dir(:app, "priv/translations/#{locale}.yml")

    case YamlElixir.read_from_file(path) do
      {:ok, translations} ->
        json(conn, translations)

      {:error, reason} ->
        conn
        |> put_status(:internal_server_error)
        |> json(%{error: "Could not load translations: #{inspect(reason)}"})
    end
  end
end
