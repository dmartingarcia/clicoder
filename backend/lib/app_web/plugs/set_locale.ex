defmodule AppWeb.Plugs.SetLocale do
  @moduledoc """
  Detects the request locale from (in priority order):
  1. `locale` query param
  2. `Accept-Language` header
  3. Default ("es")

  Assigns `:locale` to conn.
  """

  import Plug.Conn

  @supported App.Translations.supported_locales()
  @default App.Translations.default_locale()

  def init(opts), do: opts

  def call(conn, _opts) do
    locale = from_params(conn) || from_header(conn) || @default
    assign(conn, :locale, locale)
  end

  defp from_params(conn) do
    conn = fetch_query_params(conn)
    locale = conn.params["locale"]
    if locale in @supported, do: locale
  end

  defp from_header(conn) do
    conn
    |> get_req_header("accept-language")
    |> List.first("")
    |> String.split(",")
    |> Enum.map(fn part ->
      part |> String.split(";") |> List.first() |> String.trim() |> String.slice(0, 2)
    end)
    |> Enum.find(&(&1 in @supported))
  end
end
