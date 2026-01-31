defmodule App.CommandedApplication do
  use Commanded.Application,
    otp_app: :app,
    event_store: [
      adapter: Commanded.EventStore.Adapters.EventStore,
      event_store: App.EventStore
    ]

  router(App.Router)
end
