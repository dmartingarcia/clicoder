defmodule App.Translations do
  @moduledoc """
  Loads YAML translation files at startup and exposes a t/3 helper.
  Falls back to the key itself if not found.
  """

  use GenServer

  @supported_locales ~w(es en)
  @default_locale "es"

  # ── Public API ─────────────────────────────────────────────────────────────

  def start_link(_opts), do: GenServer.start_link(__MODULE__, [], name: __MODULE__)

  @doc """
  Translate a dotted key for the given locale.
  Supports {var} interpolation.

  ## Example

      App.Translations.t("es", "auth.error_invalid_credentials")
      App.Translations.t("en", "auth.check_email_body", email: "doc@ex.com")
  """
  def t(locale, key, vars \\ []) do
    locale = if locale in @supported_locales, do: locale, else: @default_locale
    translations = GenServer.call(__MODULE__, {:get, locale})

    keys = String.split(key, ".")

    value =
      case get_in(translations, keys) do
        nil -> key
        v -> v
      end

    interpolate(value, vars)
  end

  def supported_locales, do: @supported_locales
  def default_locale, do: @default_locale

  # ── GenServer callbacks ────────────────────────────────────────────────────

  @impl true
  def init(_) do
    translations =
      @supported_locales
      |> Enum.reduce(%{}, fn locale, acc ->
        path = Application.app_dir(:app, "priv/translations/#{locale}.yml")

        case YamlElixir.read_from_file(path) do
          {:ok, data} -> Map.put(acc, locale, data)
          {:error, _} -> acc
        end
      end)

    {:ok, translations}
  end

  @impl true
  def handle_call({:get, locale}, _from, state) do
    {:reply, Map.get(state, locale, %{}), state}
  end

  # ── Private ────────────────────────────────────────────────────────────────

  defp interpolate(str, []), do: str

  defp interpolate(str, vars) do
    Enum.reduce(vars, str, fn {k, v}, acc ->
      String.replace(acc, "{#{k}}", to_string(v))
    end)
  end
end
