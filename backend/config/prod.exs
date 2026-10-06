import Config

config :swoosh, api_client: Swoosh.ApiClient.Req

config :swoosh, local: false

config :logger, level: :info

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
