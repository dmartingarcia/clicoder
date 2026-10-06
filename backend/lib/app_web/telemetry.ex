defmodule AppWeb.Telemetry do
  use Supervisor
  import Telemetry.Metrics

  def start_link(arg) do
    Supervisor.start_link(__MODULE__, arg, name: __MODULE__)
  end

  @impl true
  def init(_arg) do
    children = [
      {:telemetry_poller, measurements: periodic_measurements(), period: 10_000},
      {TelemetryMetricsPrometheus,
       metrics: metrics(), port: Application.get_env(:app, :prometheus_port, 9568)}
    ]

    Supervisor.init(children, strategy: :one_for_one)
  end

  def metrics do
    http_buckets = [5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
    db_buckets = [1, 5, 10, 25, 50, 100, 250, 500, 1000]

    [
      distribution("phoenix.endpoint.stop.duration",
        unit: {:native, :millisecond},
        reporter_options: [buckets: http_buckets]
      ),
      distribution("phoenix.router_dispatch.stop.duration",
        tags: [:route],
        unit: {:native, :millisecond},
        reporter_options: [buckets: http_buckets]
      ),
      distribution("phoenix.router_dispatch.exception.duration",
        tags: [:route],
        unit: {:native, :millisecond},
        reporter_options: [buckets: http_buckets]
      ),
      distribution("phoenix.channel_joined.duration",
        unit: {:native, :millisecond},
        reporter_options: [buckets: http_buckets]
      ),
      distribution("phoenix.channel_handled_in.duration",
        tags: [:event],
        unit: {:native, :millisecond},
        reporter_options: [buckets: http_buckets]
      ),
      sum("phoenix.socket_drain.count"),
      distribution("app.repo.query.total_time",
        unit: {:native, :millisecond},
        description: "The sum of the other measurements",
        reporter_options: [buckets: db_buckets]
      ),
      distribution("app.repo.query.decode_time",
        unit: {:native, :millisecond},
        description: "The time spent decoding the data received from the database",
        reporter_options: [buckets: db_buckets]
      ),
      distribution("app.repo.query.query_time",
        unit: {:native, :millisecond},
        description: "The time spent executing the query",
        reporter_options: [buckets: db_buckets]
      ),
      distribution("app.repo.query.queue_time",
        unit: {:native, :millisecond},
        description: "The time spent waiting for a database connection",
        reporter_options: [buckets: db_buckets]
      ),
      distribution("app.repo.query.idle_time",
        unit: {:native, :millisecond},
        description:
          "The time the connection spent waiting before being checked out for the query",
        reporter_options: [buckets: db_buckets]
      ),
      last_value("vm.memory.total", unit: {:byte, :kilobyte}),
      last_value("vm.total_run_queue_lengths.total"),
      last_value("vm.total_run_queue_lengths.cpu"),
      last_value("vm.total_run_queue_lengths.io")
    ]
  end

  defp periodic_measurements do
    [
      :memory,
      :total_run_queue_lengths
    ]
  end
end
