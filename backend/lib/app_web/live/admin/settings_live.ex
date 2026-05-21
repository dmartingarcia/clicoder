defmodule AppWeb.Admin.SettingsLive do
  use AppWeb, :live_view

  alias App.AIEngineSettings

  @engines [
    {"bert", "BERT (RigoBERTa)", "Clasificador neuronal multi-label. Requiere GPU/CPU con modelo entrenado."},
    {"dict", "Diccionario", "Reglas deterministas por términos clínicos. Sin GPU, siempre disponible."},
    {"both", "Ambos", "BERT y diccionario en paralelo. Muestra predicciones de los dos motores."}
  ]

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, engine: AIEngineSettings.get_engine(), engines: @engines, saved: false)}
  end

  @impl true
  def handle_event("set_engine", %{"engine" => engine}, socket) do
    case AIEngineSettings.set_engine(engine) do
      :ok ->
        {:noreply, assign(socket, engine: engine, saved: true)}

      {:error, reason} ->
        {:noreply, put_flash(socket, :error, reason)}
    end
  end

  @impl true
  def render(assigns) do
    ~H"""
    <div class="p-6 max-w-xl">
      <h1 class="text-2xl font-bold text-gray-800 mb-2">Configuración</h1>
      <p class="text-gray-500 text-sm mb-6">
        Ajustes globales del sistema. Los cambios se aplican de inmediato pero
        se pierden al reiniciar el servidor.
      </p>

      <div class="bg-white rounded-lg shadow p-6">
        <h2 class="text-lg font-semibold text-gray-700 mb-1">Motor de IA</h2>
        <p class="text-gray-500 text-sm mb-4">
          Selecciona qué motor se usa para analizar los informes clínicos.
        </p>

        <div class="flex flex-col gap-3">
          <%= for {value, label, description} <- @engines do %>
            <button
              phx-click="set_engine"
              phx-value-engine={value}
              class={[
                "text-left border rounded-lg px-4 py-3 transition-colors",
                if(@engine == value,
                  do: "border-indigo-500 bg-indigo-50 ring-1 ring-indigo-400",
                  else: "border-gray-200 hover:border-indigo-300 hover:bg-gray-50"
                )
              ]}
            >
              <div class="flex items-center gap-2">
                <span class={[
                  "w-3 h-3 rounded-full flex-shrink-0",
                  if(@engine == value, do: "bg-indigo-500", else: "bg-gray-300")
                ]} />
                <span class="font-medium text-gray-800"><%= label %></span>
                <%= if @engine == value do %>
                  <span class="ml-auto text-xs text-indigo-600 font-semibold">Activo</span>
                <% end %>
              </div>
              <p class="text-xs text-gray-500 mt-1 ml-5"><%= description %></p>
            </button>
          <% end %>
        </div>

        <%= if @saved do %>
          <p class="mt-4 text-sm text-green-600">Motor actualizado correctamente.</p>
        <% end %>
      </div>
    </div>
    """
  end
end
