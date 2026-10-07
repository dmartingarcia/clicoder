defmodule AppWeb.Plugs.RateLimitTest do
  use ExUnit.Case, async: false

  import Plug.Conn

  alias AppWeb.Plugs.RateLimit

  defp peticion(remote_ip, cabeceras \\ []) do
    conn = %{Plug.Test.conn(:post, "/api/auth/login") | remote_ip: remote_ip}
    Enum.reduce(cabeceras, conn, fn {k, v}, c -> put_req_header(c, k, v) end)
  end

  defp ip_unica, do: {10, :rand.uniform(250), :rand.uniform(250), :rand.uniform(250)}

  defp agotar(remote_ip, cabeceras \\ []) do
    for _ <- 1..10, do: RateLimit.call(peticion(remote_ip, cabeceras), [])
  end

  setup do
    on_exit(fn -> Application.delete_env(:app, :trust_proxy_headers) end)
  end

  test "la peticion once desde la misma IP se rechaza con 429" do
    ip = ip_unica()
    agotar(ip)
    conn = RateLimit.call(peticion(ip), [])
    assert conn.status == 429
    assert conn.halted
  end

  test "otra IP no se ve afectada" do
    agotar(ip_unica())
    refute RateLimit.call(peticion(ip_unica()), []).halted
  end

  test "sin confiar en el proxy se ignora CF-Connecting-IP" do
    ip = ip_unica()
    agotar(ip, [{"cf-connecting-ip", "203.0.113.1"}])
    conn = RateLimit.call(peticion(ip, [{"cf-connecting-ip", "203.0.113.2"}]), [])
    assert conn.halted
  end

  describe "confiando en el proxy" do
    setup do
      Application.put_env(:app, :trust_proxy_headers, true)
    end

    test "clientes distintos detras del mismo proxy tienen cubos distintos" do
      proxy = ip_unica()
      cliente_a = "198.51.100.#{:rand.uniform(250)}"
      cliente_b = "192.0.2.#{:rand.uniform(250)}"
      agotar(proxy, [{"cf-connecting-ip", cliente_a}])

      assert RateLimit.call(peticion(proxy, [{"cf-connecting-ip", cliente_a}]), []).halted
      refute RateLimit.call(peticion(proxy, [{"cf-connecting-ip", cliente_b}]), []).halted
    end

    test "el mismo cliente comparte cubo aunque cambie la IP del proxy" do
      cliente = "198.51.100.#{:rand.uniform(250)}"
      agotar(ip_unica(), [{"cf-connecting-ip", cliente}])

      assert RateLimit.call(peticion(ip_unica(), [{"cf-connecting-ip", cliente}]), []).halted
    end

    test "sin la cabecera se usa la IP remota" do
      ip = ip_unica()
      agotar(ip)
      assert RateLimit.call(peticion(ip), []).halted
    end
  end
end
