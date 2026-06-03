defmodule AppWeb.Plugs.RateLimit do
  @moduledoc "Rate limiting basado en ETS. 10 peticiones por IP cada 60 segundos."

  import Plug.Conn

  @table :rate_limit_buckets
  @max_requests 10
  @window_ms 60_000

  def init(opts), do: opts

  def call(conn, _opts) do
    key = ip_key(conn)
    now = System.system_time(:millisecond)

    case check_rate(key, now) do
      :ok ->
        conn

      :deny ->
        conn
        |> put_status(:too_many_requests)
        |> Phoenix.Controller.json(%{error: "Demasiados intentos. Inténtalo en un minuto."})
        |> halt()
    end
  end

  defp ip_key(conn) do
    conn.remote_ip |> :inet.ntoa() |> to_string()
  end

  defp check_rate(key, now) do
    ensure_table()
    window_start = now - @window_ms

    recent =
      case :ets.lookup(@table, key) do
        [{_, timestamps}] -> Enum.filter(timestamps, &(&1 > window_start))
        [] -> []
      end

    if length(recent) >= @max_requests do
      :deny
    else
      :ets.insert(@table, {key, [now | recent]})
      :ok
    end
  end

  defp ensure_table do
    try do
      :ets.new(@table, [:named_table, :public, :set, write_concurrency: true])
    catch
      :error, :badarg -> :ok
    end
  end
end
