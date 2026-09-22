defmodule AppWeb.Admin.SettingsLive do
  use AppWeb, :live_view

  alias App.AIEngineSettings
  alias App.SummarizerSettings

  @engines [
    {"bert", "BERT (RigoBERTa)",
     "Clasificador neuronal multi-label. Requiere GPU/CPU con modelo entrenado."},
    {"dict", "Diccionario",
     "Reglas deterministas por términos clínicos. Sin GPU, siempre disponible."},
    {"both", "Ambos", "BERT y diccionario en paralelo. Muestra predicciones de los dos motores."},
    {"fused", "Fusionado",
     "Combina las puntuaciones de ambos antes de ordenar, en vez de concatenar sus listas."}
  ]

  # Las cuatro estrategias devuelven términos medidos de verdad; lo que cambia es a cuántas
  # palabras se pregunta, y eso son dos órdenes de magnitud de diferencia en tiempo.
  @explain_methods [
    {"diccionario", "Diccionario",
     "Instantáneo. Devuelve las frases clínicas que hicieron coincidencia, sin usar el modelo."},
    {"gradiente_filtrado", "Gradiente filtrado",
     "Recomendado. El gradiente elige a qué palabras preguntar y se miden solo esas."},
    {"exhaustivo", "Exhaustivo",
     "Pregunta por todas las palabras. Es la referencia fiel y la más lenta."},
    {"divide_y_venceras", "Divide y vencerás",
     "Experimental. Medido como más lento que el exhaustivo en este corpus."}
  ]

  @summarizer_models [
    {"none", "Desactivado", "No se genera resumen ni paráfrasis."},
    {"gemma4", "Gemma 4 E4B Q4_K_M", "Modelo más rápido (~2.5 GB). Recomendado."},
    {"gemma3", "Gemma 3 4B IT Q4_K_M", "Modelo anterior de Google (~2.5 GB)."},
    {"phi4", "Phi-4 Mini Instruct Q4_K_M", "Microsoft, buen equilibrio (~2.4 GB)."},
    {"qwen", "Qwen 2.5 3B Instruct Q4_K_M", "Modelo ligero (~2.0 GB)."}
  ]

  @summarizer_modes [
    {"summary", "Resumen", "Resumen conciso (~120 palabras) con los puntos clave."},
    {"paraphrase", "Paráfrasis",
     "Reformulación estructurada conservando todos los detalles clínicos."}
  ]

  @impl true
  def mount(_params, _session, socket) do
    summ = SummarizerSettings.get()

    {:ok,
     assign(socket,
       engine: AIEngineSettings.get_engine(),
       engines: @engines,
       explain_method: AIEngineSettings.get_explain_method(),
       explain_methods: @explain_methods,
       explain_saved: false,
       summarizer_model: summ.model,
       summarizer_mode: summ.mode,
       prompt_summary: summ.prompt_summary,
       prompt_paraphrase: summ.prompt_paraphrase,
       user_prompt_summary: summ.user_prompt_summary,
       user_prompt_paraphrase: summ.user_prompt_paraphrase,
       summarizer_models: @summarizer_models,
       summarizer_modes: @summarizer_modes,
       engine_saved: false,
       summarizer_saved: false,
       summarizer_error: nil
     )}
  end

  @impl true
  def handle_event("set_explain_method", %{"method" => metodo}, socket) do
    case AIEngineSettings.set_explain_method(metodo) do
      :ok -> {:noreply, assign(socket, explain_method: metodo, explain_saved: true)}
      {:error, razon} -> {:noreply, put_flash(socket, :error, razon)}
    end
  end

  def handle_event("set_engine", %{"engine" => engine}, socket) do
    case AIEngineSettings.set_engine(engine) do
      :ok ->
        {:noreply, assign(socket, engine: engine, engine_saved: true)}

      {:error, reason} ->
        {:noreply, put_flash(socket, :error, reason)}
    end
  end

  @impl true
  def handle_event(
        "set_summarizer",
        %{
          "model" => model,
          "mode" => mode,
          "prompt_summary" => ps,
          "prompt_paraphrase" => pp,
          "user_prompt_summary" => ups,
          "user_prompt_paraphrase" => upp
        },
        socket
      ) do
    with :ok <- SummarizerSettings.set_model(model),
         :ok <- SummarizerSettings.set_mode(mode),
         :ok <- SummarizerSettings.set_prompts(ps, pp, ups, upp) do
      ai_url = Application.get_env(:app, :ai_engine_url, "http://localhost:8000")

      {system_prompt, user_prompt} =
        if mode == "summary", do: {ps, ups}, else: {pp, upp}

      case Req.post("#{ai_url}/admin/summarizer",
             json: %{
               model: model,
               mode: mode,
               system_prompt: system_prompt,
               user_prompt: user_prompt
             },
             receive_timeout: 120_000
           ) do
        {:ok, %{status: 200}} ->
          {:noreply,
           assign(socket,
             summarizer_model: model,
             summarizer_mode: mode,
             prompt_summary: ps,
             prompt_paraphrase: pp,
             user_prompt_summary: ups,
             user_prompt_paraphrase: upp,
             summarizer_saved: true,
             summarizer_error: nil
           )}

        {:ok, %{status: _, body: body}} ->
          {:noreply, assign(socket, summarizer_error: body["detail"] || "Error desconocido")}

        {:error, reason} ->
          {:noreply,
           assign(socket,
             summarizer_error: "No se pudo contactar con el AI engine: #{inspect(reason)}"
           )}
      end
    else
      {:error, reason} ->
        {:noreply, put_flash(socket, :error, reason)}
    end
  end

  @impl true
  def render(assigns) do
    ~H"""
    <div class="p-6 max-w-xl space-y-8">
      <div>
        <h1 class="text-2xl font-bold text-gray-800 mb-2">Configuración</h1>
        <p class="text-gray-500 text-sm">
          Ajustes globales del sistema. Los cambios se aplican de inmediato pero
          se pierden al reiniciar el servidor.
        </p>
      </div>

      <%!-- Motor de IA --%>
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
                  "w-3 h-3 rounded-full shrink-0",
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

        <%= if @engine_saved do %>
          <p class="mt-4 text-sm text-green-600">Motor actualizado correctamente.</p>
        <% end %>
      </div>

      <%!-- Estrategia de explicabilidad --%>
      <div class="bg-white rounded-lg shadow p-6">
        <h2 class="text-lg font-semibold text-gray-700 mb-1">Explicabilidad</h2>
        <p class="text-gray-500 text-sm mb-5">
          Cómo se calculan los términos del informe que justifican cada código. Se piden en una
          segunda llamada, de modo que los códigos se muestran sin esperar a ellos. Las cuatro
          estrategias devuelven términos medidos de verdad: lo que cambia es a cuántas palabras
          se pregunta, y con ello el tiempo de respuesta.
        </p>

        <div class="flex flex-col gap-3">
          <%= for {value, label, description} <- @explain_methods do %>
            <button
              phx-click="set_explain_method"
              phx-value-method={value}
              class={[
                "text-left border rounded-lg px-4 py-3 transition-colors",
                if(@explain_method == value,
                  do: "border-indigo-500 bg-indigo-50 ring-1 ring-indigo-400",
                  else: "border-gray-200 hover:border-indigo-300 hover:bg-gray-50"
                )
              ]}
            >
              <div class="flex items-center gap-2">
                <span class={[
                  "w-3 h-3 rounded-full shrink-0",
                  if(@explain_method == value, do: "bg-indigo-500", else: "bg-gray-300")
                ]} />
                <span class="font-medium text-gray-800"><%= label %></span>
                <%= if @explain_method == value do %>
                  <span class="ml-auto text-xs text-indigo-600 font-semibold">Activo</span>
                <% end %>
              </div>
              <p class="text-xs text-gray-500 mt-1 ml-5"><%= description %></p>
            </button>
          <% end %>
        </div>

        <%= if @explain_saved do %>
          <p class="mt-4 text-sm text-green-600">Estrategia actualizada correctamente.</p>
        <% end %>
      </div>

      <%!-- Summarizer LLM --%>
      <div class="bg-white rounded-lg shadow p-6">
        <h2 class="text-lg font-semibold text-gray-700 mb-1">Summarizer LLM</h2>
        <p class="text-gray-500 text-sm mb-5">
          Modelo de lenguaje local para generar el resumen o paráfrasis del informe.
          El cambio recarga el modelo en memoria (puede tardar 10-30 s).
        </p>

        <form phx-submit="set_summarizer" class="space-y-5">
          <%!-- Modelo --%>
          <div>
            <p class="text-sm font-medium text-gray-700 mb-2">Modelo</p>
            <div class="flex flex-col gap-2">
              <%= for {value, label, description} <- @summarizer_models do %>
                <label class={[
                  "flex items-start gap-3 border rounded-lg px-4 py-3 cursor-pointer transition-colors",
                  if(@summarizer_model == value,
                    do: "border-indigo-500 bg-indigo-50 ring-1 ring-indigo-400",
                    else: "border-gray-200 hover:border-indigo-300 hover:bg-gray-50"
                  )
                ]}>
                  <input
                    type="radio"
                    name="model"
                    value={value}
                    checked={@summarizer_model == value}
                    class="mt-0.5 accent-indigo-600"
                  />
                  <div>
                    <p class="text-sm font-medium text-gray-800"><%= label %></p>
                    <p class="text-xs text-gray-500"><%= description %></p>
                  </div>
                </label>
              <% end %>
            </div>
          </div>

          <%!-- Modo --%>
          <div>
            <p class="text-sm font-medium text-gray-700 mb-2">Modo de salida</p>
            <div class="flex flex-col gap-2">
              <%= for {value, label, description} <- @summarizer_modes do %>
                <label class={[
                  "flex items-start gap-3 border rounded-lg px-4 py-3 cursor-pointer transition-colors",
                  if(@summarizer_mode == value,
                    do: "border-indigo-500 bg-indigo-50 ring-1 ring-indigo-400",
                    else: "border-gray-200 hover:border-indigo-300 hover:bg-gray-50"
                  )
                ]}>
                  <input
                    type="radio"
                    name="mode"
                    value={value}
                    checked={@summarizer_mode == value}
                    class="mt-0.5 accent-indigo-600"
                  />
                  <div>
                    <p class="text-sm font-medium text-gray-800"><%= label %></p>
                    <p class="text-xs text-gray-500"><%= description %></p>
                  </div>
                </label>
              <% end %>
            </div>
          </div>

          <%!-- Nota de variables --%>
          <div class="rounded-lg bg-indigo-50 border border-indigo-100 px-4 py-3 text-xs text-indigo-700 space-y-0.5">
            <p class="font-medium mb-1">Variables disponibles en los prompts:</p>
            <p><code class="bg-white px-1 rounded border border-indigo-200">&#123;language&#125;</code> — idioma del usuario (ej. <em>español</em>, <em>English</em>). Se interpola en el backend antes de llamar al modelo.</p>
            <p><code class="bg-white px-1 rounded border border-indigo-200">&#123;text&#125;</code> — informe clínico del paciente.</p>
          </div>

          <%!-- System prompts --%>
          <div>
            <p class="text-sm font-medium text-gray-700 mb-1">System prompt — resumen</p>
            <p class="text-xs text-gray-400 mb-2">Instrucciones del sistema para generar el análisis CIE-10 + resumen. Acepta <code class="bg-gray-100 px-1 rounded">&#123;language&#125;</code>.</p>
            <textarea
              name="prompt_summary"
              rows="4"
              class="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 text-gray-700 focus:outline-none focus:ring-1 focus:ring-indigo-400 resize-y"
            ><%= @prompt_summary %></textarea>
          </div>

          <div>
            <p class="text-sm font-medium text-gray-700 mb-1">System prompt — paráfrasis</p>
            <p class="text-xs text-gray-400 mb-2">Instrucciones del sistema para reformular el informe. Acepta <code class="bg-gray-100 px-1 rounded">&#123;language&#125;</code>.</p>
            <textarea
              name="prompt_paraphrase"
              rows="4"
              class="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 text-gray-700 focus:outline-none focus:ring-1 focus:ring-indigo-400 resize-y"
            ><%= @prompt_paraphrase %></textarea>
          </div>

          <div>
            <p class="text-sm font-medium text-gray-700 mb-1">User prompt — resumen</p>
            <p class="text-xs text-gray-400 mb-2">
              Usa <code class="bg-gray-100 px-1 rounded">&#123;text&#125;</code> donde debe aparecer el informe y <code class="bg-gray-100 px-1 rounded">&#123;language&#125;</code> para el idioma del usuario.
            </p>
            <textarea
              name="user_prompt_summary"
              rows="7"
              class="w-full text-sm font-mono border border-gray-300 rounded-lg px-3 py-2 text-gray-700 focus:outline-none focus:ring-1 focus:ring-indigo-400 resize-y"
            ><%= @user_prompt_summary %></textarea>
          </div>

          <div>
            <p class="text-sm font-medium text-gray-700 mb-1">User prompt — paráfrasis</p>
            <p class="text-xs text-gray-400 mb-2">
              Usa <code class="bg-gray-100 px-1 rounded">&#123;text&#125;</code> donde debe aparecer el informe y <code class="bg-gray-100 px-1 rounded">&#123;language&#125;</code> para el idioma del usuario.
            </p>
            <textarea
              name="user_prompt_paraphrase"
              rows="7"
              class="w-full text-sm font-mono border border-gray-300 rounded-lg px-3 py-2 text-gray-700 focus:outline-none focus:ring-1 focus:ring-indigo-400 resize-y"
            ><%= @user_prompt_paraphrase %></textarea>
          </div>

          <button
            type="submit"
            class="w-full bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            Aplicar y recargar modelo
          </button>
        </form>

        <%= if @summarizer_saved do %>
          <p class="mt-4 text-sm text-green-600">Summarizer recargado correctamente.</p>
        <% end %>
        <%= if @summarizer_error do %>
          <p class="mt-4 text-sm text-red-600"><%= @summarizer_error %></p>
        <% end %>
      </div>
    </div>
    """
  end
end
