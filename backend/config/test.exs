import Config

config :app, App.Repo,
  url:
    System.get_env("TEST_DATABASE_URL", "postgresql://postgres:changeme@db:5432/cie10_app_test"),
  pool: Ecto.Adapters.SQL.Sandbox,
  pool_size: System.schedulers_online() * 2

config :app, App.EventStore,
  serializer: App.JsonSerializer,
  url:
    System.get_env(
      "TEST_EVENT_STORE_URL",
      "postgresql://postgres:changeme@db:5432/cie10_eventstore_test"
    )

config :app, AppWeb.Endpoint,
  http: [ip: {127, 0, 0, 1}, port: 4002],
  secret_key_base: "t5l4JI2GWLy81OdkAUBUdf+THl1i5N8ilTYRG/3fGo3oG+pCm8Eu7QqKI4zkp1Kc",
  server: false

config :app, App.Mailer, adapter: Swoosh.Adapters.Test

config :swoosh, :api_client, false

config :logger, level: :warning

config :phoenix, :plug_init_mode, :runtime

# Puerto 0 = el OS elige un puerto libre; evita conflicto con el contenedor corriendo en 9568
config :app, :prometheus_port, 0

# Req.Test stub para el AI engine: vacío en prod, inyectado solo en test
config :app, :ai_req_opts, plug: {Req.Test, App.AIEngineMock}
