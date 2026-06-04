defmodule App.SummarizerSettings do
  @moduledoc """
  Feature toggle para el modelo y modo del summarizer LLM.

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

  def start_link(_opts \\ []) do
    Agent.start_link(fn -> %{model: @default_model, mode: @default_mode} end, name: __MODULE__)
  end

  @spec get() :: %{model: String.t(), mode: String.t()}
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
end
