import Config

config :app, App.Repo,
  url: System.get_env("DATABASE_URL") || "postgresql://postgres:changeme@db:5432/cie10_app",
  stacktrace: true,
  show_sensitive_data_on_connection_error: true,
  pool_size: 10

config :app, App.EventStore,
  serializer: App.JsonSerializer,
  url:
    System.get_env("EVENT_STORE_URL") || "postgresql://postgres:changeme@db:5432/cie10_eventstore"

config :app, AppWeb.Endpoint,
  # Binding to 0.0.0.0 to allow access from Docker network
  http: [ip: {0, 0, 0, 0}, port: String.to_integer(System.get_env("PORT") || "4000")],
  check_origin: false,
  code_reloader: true,
  debug_errors: true,
  secret_key_base: "iRIPjGUBVKcqO9aAVJb8x9skd/XdL4bgY13H/E7+0u++4n4UhQY6w/eArS/PbsoK",
  watchers: []

config :app, dev_routes: true

config :logger, :default_formatter, format: "[$level] $message\n"

config :phoenix, :stacktrace_depth, 20

config :phoenix, :plug_init_mode, :runtime

config :app, App.Mailer,
  adapter: Swoosh.Adapters.SMTP,
  relay: System.get_env("SMTP_HOST") || "localhost",
  port: String.to_integer(System.get_env("SMTP_PORT") || "1025"),
  tls: :never,
  auth: :never

config :swoosh, :api_client, Swoosh.ApiClient.Finch
config :swoosh, :finch_name, App.Finch
