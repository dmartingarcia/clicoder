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
        # La cadena de consulta no la cubria nada, y por ahi viajan los tokens de confirmacion
        # de correo (GET /auth/confirm/:token se comparte por enlace).
        |> Map.put(:query_string, "[FILTERED]")
        # REMOTE_ADDR es la IP del paciente o del codificador: dato personal del articulo 4
        # del RGPD, y no hace falta para diagnosticar un error.
        |> Map.update(:env, %{}, fn env ->
          if is_map(env), do: Map.drop(env, ["REMOTE_ADDR", "REMOTE_PORT"]), else: %{}
        end)
        # La clave puede existir con valor nil, y ahi Map.update no aplica el valor por defecto.
        # Si el filtro revienta, el aviso de error no se envia y el fallo original se pierde.
        |> Map.update(:headers, [], &scrub_headers/1)

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

    defp scrub_headers(headers) when is_list(headers) do
      Enum.map(headers, fn
        {h, _} when h in ["authorization", "cookie", "x-forwarded-for", "x-real-ip"] ->
          {h, "[FILTERED]"}

        h ->
          h
      end)
    end

    defp scrub_headers(_), do: []

    # Identificar a quien sufrio el error basta con el id interno: el correo y la IP no
    # aportan nada para depurar y son datos personales en manos de un tercero.
    defp scrub_user(%{user: user} = event) when is_map(user) do
      %{event | user: Map.take(user, [:id, "id"])}
    end

    defp scrub_user(event), do: event
  end
end
