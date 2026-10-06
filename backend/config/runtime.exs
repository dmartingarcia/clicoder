import Config

if System.get_env("PHX_SERVER") do
  config :app, AppWeb.Endpoint, server: true
end

if config_env() == :prod do
  case System.get_env("SENTRY_DSN") do
    dsn when is_binary(dsn) and dsn != "" ->
      config :sentry,
        dsn: dsn,
        environment_name: :prod

    _ ->
      :ok
  end
end

if config_env() == :prod do
  database_url =
    System.get_env("DATABASE_URL") ||
      raise """
      environment variable DATABASE_URL is missing.
      For example: ecto://USER:PASS@HOST/DATABASE
      """

  maybe_ipv6 = if System.get_env("ECTO_IPV6") in ~w(true 1), do: [:inet6], else: []

  config :app, App.Repo,
    url: database_url,
    pool_size: String.to_integer(System.get_env("POOL_SIZE") || "10"),
    socket_options: maybe_ipv6

  secret_key_base =
    System.get_env("SECRET_KEY_BASE") ||
      raise """
      environment variable SECRET_KEY_BASE is missing.
      You can generate one by calling: mix phx.gen.secret
      """

  host = System.get_env("PHX_HOST") || "example.com"
  port = String.to_integer(System.get_env("PORT") || "4000")
  domain = System.get_env("DOMAIN") || host

  config :app, :dns_cluster_query, System.get_env("DNS_CLUSTER_QUERY")

  config :app, AppWeb.Endpoint,
    url: [host: host, port: 443, scheme: "https"],
    check_origin: ["https://#{domain}", "https://#{host}"],
    http: [
      # Enable IPv6 and bind on all interfaces.
      ip: {0, 0, 0, 0, 0, 0, 0, 0},
      port: port
    ],
    secret_key_base: secret_key_base

  event_store_url =
    System.get_env("EVENT_STORE_URL") ||
      raise "environment variable EVENT_STORE_URL is missing."

  config :app, App.EventStore,
    serializer: App.JsonSerializer,
    url: event_store_url

  mailjet_api_key =
    System.get_env("MAILJET_API_KEY") ||
      raise "environment variable MAILJET_API_KEY is missing."

  mailjet_secret =
    System.get_env("MAILJET_SECRET_KEY") ||
      raise "environment variable MAILJET_SECRET_KEY is missing."

  config :app, App.Mailer,
    adapter: Swoosh.Adapters.Mailjet,
    api_key: mailjet_api_key,
    secret: mailjet_secret
end
