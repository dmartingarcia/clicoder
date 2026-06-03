# This file is responsible for configuring your application
# and its dependencies with the aid of the Config module.
#
# This configuration file is loaded before any dependency and
# is restricted to this project.

# General application configuration
import Config

config :app,
  ecto_repos: [App.Repo],
  event_stores: [App.EventStore],
  generators: [timestamp_type: :utc_datetime, binary_id: true]

# Configuración de Commanded con RabbitMQ
config :app, App.CommandedApplication,
  pubsub: :local,
  registry: :local

# Configures the endpoint
config :app, AppWeb.Endpoint,
  url: [host: "localhost"],
  adapter: Bandit.PhoenixAdapter,
  render_errors: [
    formats: [json: AppWeb.ErrorJSON],
    layout: false
  ],
  pubsub_server: App.PubSub,
  live_view: [signing_salt: "jO6SKDbz"]

# Configures the mailer
#
# By default it uses the "Local" adapter which stores the emails
# locally. You can see the emails in your browser, at "/dev/mailbox".
#
# For production it's recommended to configure a different adapter
# at the `config/runtime.exs`.
config :app, App.Mailer, adapter: Swoosh.Adapters.Local

# URL del microservicio de IA
config :app, :ai_engine_url, System.get_env("AI_ENGINE_URL") || "http://localhost:8000"

# Configures Elixir's Logger
config :logger, :default_formatter,
  format: "$time $metadata[$level] $message\n",
  metadata: [
    :request_id,
    :conversation_id,
    :message_id,
    :ai_url,
    :engine,
    :status,
    :body,
    :reason,
    :classifier_ms,
    :summarizer_ms,
    :total_ms
  ]

# Use Jason for JSON parsing in Phoenix
config :phoenix, :json_library, Jason

# Sentry — base config (DSN en runtime.exs)
config :sentry,
  enable_source_code_context: true,
  root_source_code_paths: [File.cwd!()],
  tags: %{app: "cie10-backend"},
  filter_keys: [
    :password,
    :password_hash,
    :token,
    :content,
    :report_text,
    :authorization,
    :cookie
  ],
  before_send: {AppWeb.SentryFilter, :filter_event}

# Import environment specific config. This must remain at the bottom
# of this file so it overrides the configuration defined above.
import_config "#{config_env()}.exs"
