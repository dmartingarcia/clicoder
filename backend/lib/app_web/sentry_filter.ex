if Code.ensure_loaded?(Sentry) do
  defmodule AppWeb.SentryFilter do
    @scrub_fields ~w(password password_hash token content report_text authorization cookie)

    def filter_event(%Sentry.Event{} = event) do
      event |> scrub_request() |> scrub_extra()
    end

    defp scrub_request(%{request: request} = event) when not is_nil(request) do
      scrubbed =
        request
        |> Map.update(:body_params, %{}, &scrub_map/1)
        |> Map.update(:headers, [], fn headers ->
          Enum.map(headers, fn
            {"authorization", _} -> {"authorization", "[FILTERED]"}
            {"cookie", _} -> {"cookie", "[FILTERED]"}
            h -> h
          end)
        end)

      %{event | request: scrubbed}
    end

    defp scrub_request(event), do: event

    defp scrub_extra(%{extra: extra} = event) when is_map(extra) do
      %{event | extra: scrub_map(extra)}
    end

    defp scrub_extra(event), do: event

    defp scrub_map(map) when is_map(map) do
      Map.new(map, fn
        {k, _v} when k in @scrub_fields -> {k, "[FILTERED]"}
        {k, v} when is_map(v) -> {k, scrub_map(v)}
        kv -> kv
      end)
    end

    defp scrub_map(other), do: other
  end
end
