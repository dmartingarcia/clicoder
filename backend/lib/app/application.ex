defmodule App.Application do
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    if Application.get_env(:sentry, :dsn) do
      :logger.add_handler(:sentry_handler, Sentry.LoggerHandler, %{})
    end

    children = [
      AppWeb.Telemetry,
      App.Repo,
      {DNSCluster, query: Application.get_env(:app, :dns_cluster_query) || :ignore},
      {Phoenix.PubSub, name: App.PubSub},
      {Finch, name: App.Finch},
      App.Translations,
      App.AIEngineSettings,
      App.SummarizerSettings,
      App.CommandedApplication,
      App.Projections.ConversationProjector,
      AppWeb.Endpoint
    ]

    opts = [strategy: :one_for_one, name: App.Supervisor]
    Supervisor.start_link(children, opts)
  end

  @impl true
  def config_change(changed, _new, removed) do
    AppWeb.Endpoint.config_change(changed, removed)
    :ok
  end
end
