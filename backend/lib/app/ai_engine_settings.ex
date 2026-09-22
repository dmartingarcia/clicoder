defmodule App.AIEngineSettings do
  @moduledoc """
  Feature toggles del motor de IA: qué motor analiza los informes y cómo se explican.

  Mantiene los ajustes en memoria mediante un `Agent`. Se pierden al reiniciar el nodo y
  vuelven a sus valores por defecto.

  Solo funcional en deploys mono-instancia. Para setups distribuidos se debería migrar a una solución centralizada (DB, Redis, etc).

  Motores: `"bert"` | `"dict"` | `"both"` | `"fused"`
  Métodos de explicabilidad: `"diccionario"` | `"gradiente_filtrado"` | `"exhaustivo"` | `"divide_y_venceras"`
  """

  use Agent

  @valid_engines ~w(bert dict both fused)
  @default_engine "bert"

  @valid_explain ~w(diccionario gradiente_filtrado exhaustivo divide_y_venceras)
  @default_explain "gradiente_filtrado"

  def start_link(_opts \\ []) do
    Agent.start_link(fn -> %{engine: @default_engine, explain: @default_explain} end,
      name: __MODULE__
    )
  end

  @doc "Devuelve el motor activo (\"bert\" | \"dict\" | \"both\" | \"fused\")."
  @spec get_engine() :: String.t()
  def get_engine, do: Agent.get(__MODULE__, & &1.engine)

  @doc "Cambia el motor activo. Devuelve :ok o {:error, razón}."
  @spec set_engine(String.t()) :: :ok | {:error, term()}
  def set_engine(engine) when engine in @valid_engines do
    Agent.update(__MODULE__, &Map.put(&1, :engine, engine))
  end

  def set_engine(engine), do: {:error, "Motor inválido: #{engine}"}

  @doc """
  Devuelve la estrategia de atribución activa.

  Gobierna el coste de la segunda llamada, la que calcula los términos que justifican cada
  código. Las cuatro devuelven términos reales, pero difieren dos órdenes de magnitud en
  tiempo, de modo que la elección es un compromiso entre rapidez y exhaustividad y no entre
  correcto e incorrecto.
  """
  @spec get_explain_method() :: String.t()
  def get_explain_method, do: Agent.get(__MODULE__, & &1.explain)

  @doc "Cambia la estrategia de atribución. Devuelve :ok o {:error, razón}."
  @spec set_explain_method(String.t()) :: :ok | {:error, term()}
  def set_explain_method(metodo) when metodo in @valid_explain do
    Agent.update(__MODULE__, &Map.put(&1, :explain, metodo))
  end

  def set_explain_method(metodo), do: {:error, "Método inválido: #{metodo}"}
end
