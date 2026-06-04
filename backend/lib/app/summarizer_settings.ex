defmodule App.SummarizerSettings do
  @moduledoc """
  Feature toggle para el modelo, modo y system prompts del summarizer LLM.

  Mantiene la config en memoria via `Agent`. Se pierde al reiniciar.

  Modelos válidos: `"gemma3"` | `"gemma4"` | `"phi4"` | `"qwen"` | `"none"`
  Modos válidos:   `"summary"` | `"paraphrase"`

  Solo funcional en deploys mono-instancia. Para setups distribuidos se debería migrar a una solución centralizada (DB, Redis, etc).
  """

  use Agent

  @valid_models ~w(gemma3 gemma4 phi4 qwen none)
  @valid_modes ~w(summary paraphrase)
  @default_model "none"
  @default_mode "summary"

  # Defaults
  @default_prompt_summary (
    "Eres un médico especialista en documentación clínica. " <>
    "Tu tarea es resumir informes clínicos de forma concisa y estructurada. " <>
    "Responde siempre en español. No añadas comentarios ni explicaciones fuera del resumen."
  )
  @default_prompt_paraphrase (
    "Eres un médico especialista en documentación clínica. " <>
    "Tu tarea es reformular informes clínicos de forma clara y estructurada, " <>
    "conservando TODOS los detalles médicos: diagnósticos, fármacos, dosis, fechas y procedimientos. " <>
    "Responde siempre en español. No añadas ni omitas información médica."
  )
  @default_user_summary (
    "Resume el siguiente informe clínico desde un punto de vista médico.\n" <>
    "Incluye: motivo de consulta, antecedentes relevantes, hallazgos exploratorios y analíticos, " <>
    "diagnóstico principal y procedimientos realizados. Máximo 120 palabras. Sin listas, en prosa continua.\n\n" <>
    "Informe:\n{text}\n\nResumen médico:"
  )
  @default_user_paraphrase (
    "Reformula el siguiente informe clínico de forma clara y estructurada.\n" <>
    "Organiza la información en estas secciones (sin encabezados, en prosa continua): " <>
    "antecedentes y motivo de consulta, evolución clínica, hallazgos diagnósticos, " <>
    "tratamiento y procedimientos. Conserva TODOS los datos médicos exactos.\n\n" <>
    "Informe:\n{text}\n\nInforme reformulado:"
  )

  def start_link(_opts \\ []) do
    Agent.start_link(
      fn ->
        %{
          model: @default_model,
          mode: @default_mode,
          prompt_summary: @default_prompt_summary,
          prompt_paraphrase: @default_prompt_paraphrase,
          user_prompt_summary: @default_user_summary,
          user_prompt_paraphrase: @default_user_paraphrase
        }
      end,
      name: __MODULE__
    )
  end

  @spec get() :: map()
  def get, do: Agent.get(__MODULE__, & &1)

  @spec set_model(String.t()) :: :ok | {:error, term()}
  def set_model(model) when model in @valid_models do
    Agent.update(__MODULE__, &Map.put(&1, :model, model))
  end

  def set_model(model), do: {:error, "Modelo inválido: #{model}"}

  @spec set_mode(String.t()) :: :ok | {:error, term()}
  def set_mode(mode) when mode in @valid_modes do
    Agent.update(__MODULE__, &Map.put(&1, :mode, mode))
  end

  def set_mode(mode), do: {:error, "Modo inválido: #{mode}"}

  @spec set_prompts(String.t(), String.t(), String.t(), String.t()) :: :ok
  def set_prompts(prompt_summary, prompt_paraphrase, user_prompt_summary, user_prompt_paraphrase) do
    Agent.update(__MODULE__, fn state ->
      %{state |
        prompt_summary: prompt_summary,
        prompt_paraphrase: prompt_paraphrase,
        user_prompt_summary: user_prompt_summary,
        user_prompt_paraphrase: user_prompt_paraphrase
      }
    end)
  end
end
