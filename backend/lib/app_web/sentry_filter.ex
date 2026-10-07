if Code.ensure_loaded?(Sentry) do
  defmodule AppWeb.SentryFilter do
    @scrub_fields ~w(password password_hash token content report_text authorization cookie)

    def filter_event(%Sentry.Event{} = event) do
      event |> scrub_request() |> scrub_extra() |> scrub_user()
    end

    defp scrub_request(%{request: request} = event) when not is_nil(request) do
      scrubbed =
        request
        |> Map.update(:body_params, %{}, fn b -> if is_map(b), do: scrub_map(b), else: %{} end)
        # La query string no estaba cubierta y lleva los tokens de confirmacion de correo.
        |> Map.put(:query_string, "[FILTERED]")
        |> Map.update(:url, nil, &scrub_path/1)
        # REMOTE_ADDR es dato personal (art. 4 RGPD) y no hace falta para diagnosticar.
        |> Map.update(:env, %{}, fn env ->
          if is_map(env),
            do:
              env
              |> Map.drop(["REMOTE_ADDR", "REMOTE_PORT"])
              |> Map.new(fn {k, v} -> {k, scrub_path(v)} end),
            else: %{}
        end)
        # La clave puede existir con nil (Map.update no aplica el defecto); si el filtro revienta, se pierde el aviso.
        |> Map.update(:headers, [], &scrub_headers/1)

      %{event | request: scrubbed}
    end

    defp scrub_request(event), do: event

    defp scrub_path(value) when is_binary(value),
      do: Regex.replace(~r{/auth/confirm/[^/?#\s]+}, value, "/auth/confirm/[FILTERED]")

    defp scrub_path(value), do: value

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

    defp scrub_headers(headers) when is_list(headers) do
      Enum.map(headers, fn
        {h, _} when h in ["authorization", "cookie", "x-forwarded-for", "x-real-ip"] ->
          {h, "[FILTERED]"}

        h ->
          h
      end)
    end

    defp scrub_headers(_), do: []

    # Basta el id interno: correo e IP son datos personales en manos de un tercero.
    defp scrub_user(%{user: user} = event) when is_map(user) do
      %{event | user: Map.take(user, [:id, "id"])}
    end

    defp scrub_user(event), do: event
  end
end
