defmodule App.AIEngineSettings do
  @moduledoc """
  Feature toggles del motor de IA: qué motor analiza los informes y cómo se explican.

  Mantiene los ajustes en memoria mediante un `Agent`. Los dos se tratan distinto a propósito:

  - El **motor** es volátil. Vuelve a `"bert"` en cada arranque porque sirve para comparar
    motores durante la evaluación, no como configuración permanente.
  - El **método de explicabilidad** se persiste en la tabla `settings`. No es un experimento
    sino una elección de calidad y coste, y si no se guardara el sistema cambiaría de
    comportamiento tras un reinicio sin que nadie lo hubiera tocado.

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
    Agent.start_link(fn -> %{engine: @default_engine, explain: explain_guardado()} end,
      name: __MODULE__
    )
  end

  # Si la tabla no existe todavia (arranque antes de migrar) o la consulta falla, se arranca
  # con el valor por defecto en vez de impedir que suba el nodo.
  defp explain_guardado do
    case App.Settings.load() do
      %{explain_method: metodo} when metodo in @valid_explain -> metodo
      _ -> @default_explain
    end
  rescue
    _ -> @default_explain
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
    persistir_explain(metodo)
  end

  def set_explain_method(metodo), do: {:error, "Método inválido: #{metodo}"}
  # Se guarda fuera de la llamada para que cambiar de metodo desde el panel responda al
  # instante aunque la base de datos vaya lenta.
  defp persistir_explain(metodo) do
    Task.start(fn ->
      # La fila de ajustes exige modelo y modo del resumidor, asi que en una instalacion
      # nueva, sin fila todavia, guardar solo el metodo fallaria. Se acompana de los valores
      # vigentes del resumidor, que en una actualizacion son los que ya estaban.
      try do
        summ = App.SummarizerSettings.get()

        App.Settings.save(%{
          explain_method: metodo,
          summarizer_model: summ.model,
          summarizer_mode: summ.mode
        })
      rescue
        _ -> :ok
      end
    end)

    :ok
  end
end
