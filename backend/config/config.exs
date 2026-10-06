import Config

config :app,
  ecto_repos: [App.Repo],
  event_stores: [App.EventStore],
  generators: [timestamp_type: :utc_datetime, binary_id: true]

config :app, App.CommandedApplication,
  pubsub: :local,
  registry: :local

config :app, AppWeb.Endpoint,
  url: [host: "localhost"],
  adapter: Bandit.PhoenixAdapter,
  render_errors: [
    formats: [json: AppWeb.ErrorJSON],
    layout: false
  ],
  pubsub_server: App.PubSub,
  live_view: [signing_salt: "jO6SKDbz"]

config :app, App.Mailer, adapter: Swoosh.Adapters.Local

config :app, :ai_engine_url, System.get_env("AI_ENGINE_URL") || "http://localhost:8000"

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
    :total_ms,
    :explain_ms,
    :method
  ]

config :phoenix, :json_library, Jason

# Debe ir al final para que sobrescriba lo definido arriba.
import_config "#{config_env()}.exs"
