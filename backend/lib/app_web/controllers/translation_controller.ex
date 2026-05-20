defmodule AppWeb.TranslationController do
  use AppWeb, :controller
  use OpenApiSpex.ControllerSpecs

  @supported_locales ~w(es en fr it de)
  @default_locale "es"

  operation :show,
    summary: "Obtener traducciones de la UI",
    tags: ["Translations"],
    parameters: [
      OpenApiSpex.Operation.parameter(:locale, :path, :string, "Código de idioma",
        required: true,
        schema: %OpenApiSpex.Schema{type: :string, enum: ["es", "en", "fr", "it", "de"]})
    ],
    responses: [
      ok: {"Mapa de claves de traducción", "application/json", %OpenApiSpex.Schema{type: :object}}
    ]

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
