defmodule App.SummarizerSettings do
  @moduledoc """
  Feature toggle para el modelo, modo y prompts del summarizer LLM.

  Al arrancar carga la configuración desde la BD (tabla `settings`). Si no hay fila,
  usa los defaults. Cada cambio persiste en BD de forma asíncrona y actualiza el estado
  en memoria para no bloquear el Agent.

  Variables disponibles en los prompts:
    - `{text}`     — informe clínico del paciente
    - `{language}` — idioma del usuario (ej. "español", "English"), interpolado por el backend

  Modelos válidos: `"gemma3"` | `"gemma4"` | `"phi4"` | `"qwen"` | `"none"`
  Modos válidos:   `"summary"` | `"paraphrase"`
  """

  use Agent

  @valid_models ~w(gemma3 gemma4 phi4 qwen none)
  @valid_modes ~w(summary paraphrase)
  @default_model "none"
  @default_mode "summary"
  @cache_ttl_s 10

  @default_prompt_summary "Médico CIE-10. Responde en {language}. Solo análisis, sin comentarios."

  @default_prompt_paraphrase "Médico CIE-10. Reformula conservando TODOS los datos médicos. Responde en {language}."

  @default_user_summary "Informe: {text}\n\n" <>
                          "Resume (máx 80 palabras). Indica: diagnóstico, código CIE-10, palabras que lo activan y por qué.\n\n" <>
                          "Análisis:"

  @default_user_paraphrase "Informe: {text}\n\n" <>
                             "Reformula en prosa: motivo consulta, evolución, hallazgos, tratamiento. " <>
                             "Al final: código CIE-10, palabras clave que lo activan, motivo.\n\n" <>
                             "Reformulado:"

  def start_link(_opts \\ []) do
    Agent.start_link(fn -> load_initial_state() end, name: __MODULE__)
  end

  @spec get() :: map()
  def get do
    Agent.get_and_update(__MODULE__, fn state ->
      now = System.monotonic_time(:second)
      cached_at = Map.get(state, :cached_at, 0)

      if now - cached_at > @cache_ttl_s do
        fresh =
          try do
            case App.Settings.load() do
              nil -> state
              s -> state_from_db(s, state)
            end
          rescue
            _ -> state
          end

        fresh = Map.put(fresh, :cached_at, now)
        {fresh, fresh}
      else
        {state, state}
      end
    end)
  end

  @spec set_model(String.t()) :: :ok | {:error, term()}
  def set_model(model) when model in @valid_models do
    Agent.update(__MODULE__, &Map.put(&1, :model, model))
    persist_async()
  end

  def set_model(model), do: {:error, "Modelo inválido: #{model}"}

  @spec set_mode(String.t()) :: :ok | {:error, term()}
  def set_mode(mode) when mode in @valid_modes do
    Agent.update(__MODULE__, &Map.put(&1, :mode, mode))
    persist_async()
  end

  def set_mode(mode), do: {:error, "Modo inválido: #{mode}"}

  @spec set_prompts(String.t(), String.t(), String.t(), String.t()) :: :ok
  def set_prompts(prompt_summary, prompt_paraphrase, user_prompt_summary, user_prompt_paraphrase) do
    Agent.update(__MODULE__, fn state ->
      %{
        state
        | prompt_summary: prompt_summary,
          prompt_paraphrase: prompt_paraphrase,
          user_prompt_summary: user_prompt_summary,
          user_prompt_paraphrase: user_prompt_paraphrase
      }
    end)

    persist_async()
  end

  # ── Privados ────────────────────────────────────────────────────────────────

  defp load_initial_state do
    now = System.monotonic_time(:second)

    state =
      try do
        case App.Settings.load() do
          nil -> default_state()
          s -> state_from_db(s, default_state())
        end
      rescue
        _ -> default_state()
      end

    Map.put(state, :cached_at, now)
  end

  defp default_state do
    %{
      model: @default_model,
      mode: @default_mode,
      prompt_summary: @default_prompt_summary,
      prompt_paraphrase: @default_prompt_paraphrase,
      user_prompt_summary: @default_user_summary,
      user_prompt_paraphrase: @default_user_paraphrase
    }
  end

  defp state_from_db(s, fallback) do
    %{
      model: s.summarizer_model,
      mode: s.summarizer_mode,
      prompt_summary: s.prompt_summary || fallback.prompt_summary,
      prompt_paraphrase: s.prompt_paraphrase || fallback.prompt_paraphrase,
      user_prompt_summary: s.user_prompt_summary || fallback.user_prompt_summary,
      user_prompt_paraphrase: s.user_prompt_paraphrase || fallback.user_prompt_paraphrase
    }
  end

  defp persist_async do
    now = System.monotonic_time(:second)

    state =
      Agent.get_and_update(__MODULE__, fn s ->
        fresh = Map.put(s, :cached_at, now)
        {fresh, fresh}
      end)

    Task.start(fn ->
      App.Settings.save(%{
        summarizer_model: state.model,
        summarizer_mode: state.mode,
        prompt_summary: state.prompt_summary,
        prompt_paraphrase: state.prompt_paraphrase,
        user_prompt_summary: state.user_prompt_summary,
        user_prompt_paraphrase: state.user_prompt_paraphrase
      })
    end)

    :ok
  end
end
