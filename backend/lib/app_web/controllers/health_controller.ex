defmodule AppWeb.HealthController do
  use AppWeb, :controller

  def check(conn, _params) do
    json(conn, %{status: "ok"})
  end
end
