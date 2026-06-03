import Config

# Configure your database
#
# The MIX_TEST_PARTITION environment variable can be used
# to provide built-in test partitioning in CI environment.
# Run `mix help test` for more information.
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

# We don't run a server during test. If one is required,
# you can enable the server option below.
config :app, AppWeb.Endpoint,
  http: [ip: {127, 0, 0, 1}, port: 4002],
  secret_key_base: "t5l4JI2GWLy81OdkAUBUdf+THl1i5N8ilTYRG/3fGo3oG+pCm8Eu7QqKI4zkp1Kc",
  server: false

# In test we don't send emails
config :app, App.Mailer, adapter: Swoosh.Adapters.Test

# Disable swoosh api client as it is only required for production adapters
config :swoosh, :api_client, false

# Print only warnings and errors during test
config :logger, level: :warning

# Initialize plugs at runtime for faster test compilation
config :phoenix, :plug_init_mode, :runtime

# Deshabilitar Sentry en tests
config :sentry,
  included_environments: [],
  enable_source_code_context: false
