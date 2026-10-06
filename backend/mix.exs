defmodule App.MixProject do
  use Mix.Project

  def project do
    [
      app: :app,
      version: "0.1.0",
      elixir: "~> 1.19",
      elixirc_paths: elixirc_paths(Mix.env()),
      start_permanent: Mix.env() == :prod,
      aliases: aliases(),
      deps: deps(),
      listeners: [Phoenix.CodeReloader],
      test_coverage: [tool: ExCoveralls],
      dialyzer: [ignore_warnings: ".dialyzer_ignore.exs", plt_add_apps: [:sentry]],
      preferred_cli_env: [
        coveralls: :test,
        "coveralls.detail": :test,
        "coveralls.html": :test,
        "coveralls.json": :test
      ]
    ]
  end

  def application do
    [
      mod: {App.Application, []},
      extra_applications: [:logger, :runtime_tools, :os_mon]
    ]
  end

  def cli do
    [
      preferred_envs: [precommit: :test]
    ]
  end

  defp elixirc_paths(:test), do: ["lib", "test/support"]
  defp elixirc_paths(_), do: ["lib"]

  defp deps do
    [
      {:phoenix, "~> 1.8.7"},
      {:phoenix_ecto, "~> 4.5"},
      {:ecto_sql, "~> 3.13"},
      {:postgrex, ">= 0.0.0"},
      {:phoenix_live_dashboard, "~> 0.8.3"},
      # Requerido por Phoenix.LiveViewTest para inspeccionar el HTML renderizado;
      # sin él no se pueden probar las vistas del backoffice.
      {:lazy_html, ">= 0.1.0", only: :test},
      {:ecto_psql_extras, "~> 0.8"},
      {:swoosh, "~> 1.16"},
      {:req, "~> 0.5"},
      {:telemetry_metrics, "~> 1.0"},
      {:telemetry_poller, "~> 1.0"},
      {:telemetry_metrics_prometheus, "~> 1.1"},
      # Tambien en test: el filtro que impide que el informe clinico salga hacia un tercero
      # es justo lo que no puede quedarse sin probar.
      {:sentry, "~> 10.0", only: [:prod, :dev, :test], runtime: Mix.env() == :prod},
      {:gettext, "~> 1.0"},
      {:jason, "~> 1.2"},
      {:dns_cluster, "~> 0.2.0"},
      {:bandit, "~> 1.5"},
      {:commanded, "~> 1.4"},
      {:commanded_ecto_projections, "~> 1.3"},
      {:commanded_eventstore_adapter, "~> 1.4"},
      {:eventstore, "~> 1.4"},
      {:uuid, "~> 1.1"},
      {:cors_plug, "~> 3.0"},
      {:bcrypt_elixir, "~> 3.0"},
      {:finch, "~> 0.13"},
      {:gen_smtp, "~> 1.2"},
      {:yaml_elixir, "~> 2.9"},
      {:nimble_csv, "~> 1.2"},
      {:open_api_spex, "~> 3.21"},
      {:credo, "~> 1.7", only: [:dev, :test], runtime: false},
      {:dialyxir, "~> 1.4", only: [:dev, :test], runtime: false},
      {:excoveralls, "~> 0.18", only: :test}
    ]
  end

  defp aliases do
    [
      setup: ["deps.get", "ecto.setup"],
      "ecto.setup": ["ecto.create", "ecto.migrate", "run priv/repo/seeds.exs"],
      "ecto.reset": ["ecto.drop", "ecto.setup"],
      test: ["ecto.create --quiet", "ecto.migrate --quiet", "test"],
      precommit: ["compile --warning-as-errors", "deps.unlock --unused", "format", "test"],
      "test.coverage": ["coveralls.html"]
    ]
  end
end
