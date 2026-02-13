defmodule App.CommandedApplication do
  use Commanded.Application,
    otp_app: :app,
    event_store: [
      adapter: :in_memory
    ]

  router(App.Router)
end
