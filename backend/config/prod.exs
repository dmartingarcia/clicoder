import Config

# Configures Swoosh API Client
config :swoosh, api_client: Swoosh.ApiClient.Req

# Disable Swoosh Local Memory Storage
config :swoosh, local: false

# Do not print debug messages in production
config :logger, level: :info

# Sentry: solo en producción (DSN en runtime.exs)
config :sentry,
  enable_source_code_context: true,
  root_source_code_paths: [File.cwd!()],
  tags: %{app: "cie10-backend"},
  # El informe clinico no puede salir del sistema: es categoria especial del articulo 9.
  filter_keys: [
    :password,
    :password_hash,
    :token,
    :confirmation_token,
    :content,
    :report_text,
    :text,
    :email,
    :authorization,
    :cookie
  ],
  before_send: {AppWeb.SentryFilter, :filter_event}

# Runtime production configuration, including reading
# of environment variables, is done on config/runtime.exs.
