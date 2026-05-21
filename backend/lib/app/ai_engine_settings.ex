defmodule App.AIEngineSettings do
  @moduledoc """
  Feature toggle para el motor de IA del análisis de informes clínicos.

  Mantiene el ajuste en memoria mediante un `Agent`. El valor se pierde
  al reiniciar el nodo y vuelve al valor por defecto (`"bert"`).

  Valores válidos: `"bert"` | `"dict"` | `"both"`
  """

  use Agent

  @valid_engines ~w(bert dict both)
  @default "bert"

  def start_link(_opts \\ []) do
    Agent.start_link(fn -> @default end, name: __MODULE__)
  end

  @doc "Devuelve el motor activo (\"bert\" | \"dict\" | \"both\")."
  @spec get_engine() :: String.t()
  def get_engine, do: Agent.get(__MODULE__, & &1)

  @doc "Cambia el motor activo. Devuelve :ok o {:error, razón}."
  @spec set_engine(String.t()) :: :ok | {:error, term()}
  def set_engine(engine) when engine in @valid_engines do
    Agent.update(__MODULE__, fn _ -> engine end)
  end

  def set_engine(engine), do: {:error, "Motor inválido: #{engine}"}
end
