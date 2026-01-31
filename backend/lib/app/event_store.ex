defmodule App.EventStore do
  use EventStore, otp_app: :app

  # Este será nuestro EventStore para Commanded
end
