import Config

# Configures Swoosh API Client
config :swoosh, api_client: Swoosh.ApiClient.Req

# Disable Swoosh Local Memory Storage
config :swoosh, local: false

# Do not print debug messages in production
config :logger, level: :info

# Sentry — solo en producción (DSN en runtime.exs)
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

# Runtime production configuration, including reading
# of environment variables, is done on config/runtime.exs.
