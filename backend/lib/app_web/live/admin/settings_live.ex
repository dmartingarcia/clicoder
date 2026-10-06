defmodule AppWeb.Admin.SettingsLive do
  use AppWeb, :live_view

  alias App.AIEngineSettings
  alias App.SummarizerSettings

  # Cifras medidas sobre el conjunto de prueba (AnexoF). Se muestran porque "Ambos" suena mejor
  # que cada uno por separado y rinde peor que cualquiera.
  @engines [
    {"bert", "BERT (RigoBERTa)",
     "Clasificador neuronal multi-label. Requiere GPU/CPU con modelo entrenado. " <>
       "MAP 0,454 · F1 0,497."},
    {"dict", "Diccionario",
     "Reglas deterministas por términos clínicos. Sin GPU, siempre disponible. " <>
       "MAP 0,145 · F1 0,304: acierta el bloque pero no ordena dentro de él."},
    {"both", "Ambos",
     "Concatena las listas de los dos motores. Peor que cualquiera de ellos por separado " <>
       "(F1 0,285), porque hereda los falsos positivos de los dos sin ningún criterio para " <>
       "arbitrar entre ellos. Se conserva para poder contrastar los dos motores lado a lado."},
    {"fused", "Fusionado",
     "Suma la confianza del diccionario al logit del modelo antes de ordenar, en un único " <>
       "ranking. La mejor opción medida: MAP 0,554 · F1 0,610."}
  ]

  # Las cuatro devuelven terminos medidos de verdad; cambia a cuantas palabras se pregunta
  # (dos ordenes de magnitud en tiempo).
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
    {modelos, modelos_error} = cargar_catalogo_modelos()

    {:ok,
     assign(socket,
       modelos: modelos,
       modelos_error: modelos_error,
       modelo_cargando: nil,
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
  def handle_event("refrescar_modelos", _params, socket) do
    {modelos, error} = cargar_catalogo_modelos()
    {:noreply, assign(socket, modelos: modelos, modelos_error: error)}
  end

  def handle_event("cargar_modelo", %{"name" => nombre}, socket) do
    ai_url = Application.get_env(:app, :ai_engine_url, "http://localhost:8000")

    peticion =
      [json: %{name: nombre}, receive_timeout: 120_000] ++
        Application.get_env(:app, :ai_req_opts, [])

    case Req.post("#{ai_url}/admin/models", peticion) do
      {:ok, %{status: 200}} ->
        {modelos, error} = cargar_catalogo_modelos()

        {:noreply,
         socket
         |> assign(modelos: modelos, modelos_error: error, modelo_cargando: nil)
         |> put_flash(:info, "Modelo #{nombre} cargado.")}

      {:ok, %{status: _, body: body}} ->
        {:noreply, assign(socket, modelos_error: detalle_error(body), modelo_cargando: nil)}

      {:error, reason} ->
        {:noreply,
         assign(socket,
           modelos_error: "No se pudo contactar con el AI engine: #{inspect(reason)}",
           modelo_cargando: nil
         )}
    end
  end

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

      peticion = [
        json: %{
          model: model,
          mode: mode,
          system_prompt: system_prompt,
          user_prompt: user_prompt
        },
        receive_timeout: 120_000
      ]

      # Opciones de transporte inyectables para probar el panel sin levantar el motor de IA.
      case Req.post(
             "#{ai_url}/admin/summarizer",
             peticion ++ Application.get_env(:app, :ai_req_opts, [])
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
          Ajustes globales del sistema. Los cambios se aplican de inmediato. El motor
          de análisis vuelve a su valor por defecto al reiniciar el servidor, porque
          sirve para comparar durante la evaluación; el resto se conserva.
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

      <%!-- Modelo del clasificador --%>
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-start justify-between mb-1">
          <h2 class="text-lg font-semibold text-gray-700">Modelo del clasificador</h2>
          <button
            phx-click="refrescar_modelos"
            class="text-sm text-indigo-600 hover:text-indigo-800 underline"
          >
            Actualizar
          </button>
        </div>
        <p class="text-gray-500 text-sm mb-5">
          Checkpoints publicados. Cambiar de modelo es inmediato y no reinicia el servicio, pero
          uno que no esté descargado hay que traerlo antes con <code>make model-download</code>.
        </p>

        <%= if @modelos_error do %>
          <p class="text-sm text-red-600 mb-4">{@modelos_error}</p>
        <% end %>

        <%= if @modelos == [] and is_nil(@modelos_error) do %>
          <p class="text-sm text-gray-500">El motor no declara ningún modelo en su catálogo.</p>
        <% end %>

        <div class="space-y-3">
          <%= for modelo <- @modelos do %>
            <div class={
              "border rounded-lg p-4 " <>
                if(modelo["loaded"],
                  do: "border-indigo-500 bg-indigo-50",
                  else: "border-gray-200"
                )
            }>
              <div class="flex items-start justify-between gap-4">
                <div class="min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="font-medium text-gray-800">{modelo["name"]}</span>
                    <%= if modelo["loaded"] do %>
                      <span class="text-xs px-2 py-0.5 rounded-full bg-indigo-500 text-white">
                        en uso
                      </span>
                    <% end %>
                    <%= if not modelo["downloaded"] do %>
                      <span class="text-xs px-2 py-0.5 rounded-full bg-gray-200 text-gray-600">
                        sin descargar
                      </span>
                    <% end %>
                  </div>
                  <p class="text-sm text-gray-500 mt-1">{modelo["description"]}</p>
                  <%= if modelo["metrics"] not in [nil, %{}] do %>
                    <p class="text-xs text-gray-400 mt-1">
                      <%= for {clave, valor} <- modelo["metrics"] do %>
                        {clave}: {valor}&nbsp;&nbsp;
                      <% end %>
                    </p>
                  <% end %>
                </div>
                <%= if modelo["downloaded"] and not modelo["loaded"] do %>
                  <button
                    phx-click="cargar_modelo"
                    phx-value-name={modelo["name"]}
                    class="shrink-0 px-3 py-1.5 text-sm rounded-md bg-indigo-600 text-white hover:bg-indigo-700"
                  >
                    Cargar
                  </button>
                <% end %>
              </div>
            </div>
          <% end %>
        </div>
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
            <p><code class="bg-white px-1 rounded border border-indigo-200">&#123;language&#125;</code>: idioma del usuario (ej. <em>español</em>, <em>English</em>). Se interpola en el backend antes de llamar al modelo.</p>
            <p><code class="bg-white px-1 rounded border border-indigo-200">&#123;text&#125;</code>: informe clínico del paciente.</p>
          </div>

          <%!-- System prompts --%>
          <div>
            <p class="text-sm font-medium text-gray-700 mb-1">System prompt: resumen</p>
            <p class="text-xs text-gray-400 mb-2">Instrucciones del sistema para generar el análisis CIE-10 + resumen. Acepta <code class="bg-gray-100 px-1 rounded">&#123;language&#125;</code>.</p>
            <textarea
              name="prompt_summary"
              rows="4"
              class="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 text-gray-700 focus:outline-none focus:ring-1 focus:ring-indigo-400 resize-y"
            ><%= @prompt_summary %></textarea>
          </div>

          <div>
            <p class="text-sm font-medium text-gray-700 mb-1">System prompt: paráfrasis</p>
            <p class="text-xs text-gray-400 mb-2">Instrucciones del sistema para reformular el informe. Acepta <code class="bg-gray-100 px-1 rounded">&#123;language&#125;</code>.</p>
            <textarea
              name="prompt_paraphrase"
              rows="4"
              class="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 text-gray-700 focus:outline-none focus:ring-1 focus:ring-indigo-400 resize-y"
            ><%= @prompt_paraphrase %></textarea>
          </div>

          <div>
            <p class="text-sm font-medium text-gray-700 mb-1">User prompt: resumen</p>
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
            <p class="text-sm font-medium text-gray-700 mb-1">User prompt: paráfrasis</p>
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

  # El catalogo lo sirve el motor (sabe que checkpoints hay y cual esta cargado); si no
  # responde, el panel lo dice en vez de quedarse en blanco.
  defp cargar_catalogo_modelos do
    ai_url = Application.get_env(:app, :ai_engine_url, "http://localhost:8000")
    opts = [receive_timeout: 10_000] ++ Application.get_env(:app, :ai_req_opts, [])

    # El rescue es necesario: sin el, un motor caido impide abrir el panel donde se cambia de motor.
    case Req.get("#{ai_url}/admin/models", opts) do
      {:ok, %{status: 200, body: %{"models" => modelos}}} -> {modelos, nil}
      {:ok, %{status: status}} -> {[], "El motor respondio #{status} al pedir el catalogo."}
      {:error, reason} -> {[], "No se pudo contactar con el AI engine: #{inspect(reason)}"}
    end
  rescue
    e -> {[], "No se pudo contactar con el AI engine: #{Exception.message(e)}"}
  end

  defp detalle_error(%{"detail" => %{"error" => error}}), do: error
  defp detalle_error(%{"detail" => detail}) when is_binary(detail), do: detail
  defp detalle_error(_), do: "Error desconocido al cargar el modelo."
end
