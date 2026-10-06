defmodule AppWeb.Endpoint do
  use Phoenix.Endpoint, otp_app: :app

  @session_options [
    store: :cookie,
    key: "_app_key",
    signing_salt: "mMZlL4sK",
    same_site: "Lax"
  ]

  socket "/socket", AppWeb.UserSocket,
    websocket: [check_origin: false],
    longpoll: false

  socket "/live", Phoenix.LiveView.Socket,
    websocket: [connect_info: [session: @session_options]],
    longpoll: [connect_info: [session: @session_options]]

  plug Plug.Static,
    at: "/",
    from: :app,
    gzip: not code_reloading?,
    only: AppWeb.static_paths()

  plug Plug.Static,
    at: "/js/phoenix",
    from: {:phoenix, "priv/static"},
    gzip: false

  plug Plug.Static,
    at: "/js/lv",
    from: {:phoenix_live_view, "priv/static"},
    gzip: false

  if code_reloading? do
    plug Phoenix.CodeReloader
    plug Phoenix.Ecto.CheckRepoStatus, otp_app: :app
  end

  plug Phoenix.LiveDashboard.RequestLogger,
    param_key: "request_logger",
    cookie_key: "request_logger"

  plug Plug.RequestId
  plug Plug.Telemetry, event_prefix: [:phoenix, :endpoint]

  plug Plug.Parsers,
    parsers: [:urlencoded, :multipart, :json],
    pass: ["*/*"],
    json_decoder: Phoenix.json_library()

  plug Plug.MethodOverride
  plug Plug.Head
  plug Plug.Session, @session_options

  plug CORSPlug,
    origin: &AppWeb.Endpoint.cors_origins/0,
    methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    headers: ["Authorization", "Content-Type", "Accept"]

  def cors_origins do
    System.get_env("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    |> String.split(",", trim: true)
  end

  plug :put_security_headers

  if Code.ensure_loaded?(Sentry.PlugContext) do
    plug Sentry.PlugContext
  end

  plug AppWeb.Router

  defp put_security_headers(conn, _opts) do
    conn
    |> Plug.Conn.put_resp_header("x-frame-options", "DENY")
    |> Plug.Conn.put_resp_header("x-content-type-options", "nosniff")
    |> Plug.Conn.put_resp_header("referrer-policy", "strict-origin-when-cross-origin")
    |> Plug.Conn.put_resp_header(
      "strict-transport-security",
      "max-age=31536000; includeSubDomains"
    )
  end
end
