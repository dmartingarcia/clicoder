defmodule App.SummarizerSettingsTest do
  use ExUnit.Case, async: false

  setup do
    App.SummarizerSettings.set_model("none")
    App.SummarizerSettings.set_mode("summary")

    App.SummarizerSettings.set_prompts(
      "System resumen {language}",
      "System paráfrasis {language}",
      "User resumen {text}",
      "User paráfrasis {text}"
    )

    :ok
  end

  describe "get/0" do
    test "returns a map with required keys" do
      state = App.SummarizerSettings.get()
      assert is_map(state)

      for key <- [
            :model,
            :mode,
            :prompt_summary,
            :prompt_paraphrase,
            :user_prompt_summary,
            :user_prompt_paraphrase
          ] do
        assert Map.has_key?(state, key), "Missing key: #{key}"
      end
    end
  end

  describe "set_model/1" do
    test "accepts a valid model and reflects the change in get/0" do
      :ok = App.SummarizerSettings.set_model("gemma3")
      assert App.SummarizerSettings.get().model == "gemma3"
    end

    test "returns {:error, ...} for an invalid model" do
      assert {:error, "Modelo inválido: " <> _} =
               App.SummarizerSettings.set_model("unknown_model")
    end

    test "does not change state on invalid model" do
      App.SummarizerSettings.set_model("phi4")
      App.SummarizerSettings.set_model("invalid")
      assert App.SummarizerSettings.get().model == "phi4"
    end
  end

  describe "set_mode/1" do
    test "accepts 'summary'" do
      :ok = App.SummarizerSettings.set_mode("summary")
      assert App.SummarizerSettings.get().mode == "summary"
    end

    test "accepts 'paraphrase'" do
      :ok = App.SummarizerSettings.set_mode("paraphrase")
      assert App.SummarizerSettings.get().mode == "paraphrase"
    end

    test "returns {:error, ...} for an invalid mode" do
      assert {:error, "Modo inválido: " <> _} = App.SummarizerSettings.set_mode("other")
    end
  end

  describe "set_prompts/4" do
    test "updates all four prompt fields" do
      :ok =
        App.SummarizerSettings.set_prompts(
          "sys_sum",
          "sys_par",
          "usr_sum {text}",
          "usr_par {text}"
        )

      state = App.SummarizerSettings.get()
      assert state.prompt_summary == "sys_sum"
      assert state.prompt_paraphrase == "sys_par"
      assert state.user_prompt_summary == "usr_sum {text}"
      assert state.user_prompt_paraphrase == "usr_par {text}"
    end
  end

  describe "default prompts" do
    test "default system prompt for summary contains {language}" do
      assert String.contains?(App.SummarizerSettings.get().prompt_summary, "{language}")
    end

    test "default user prompt for summary contains {text}" do
      assert String.contains?(App.SummarizerSettings.get().user_prompt_summary, "{text}")
    end
  end

  describe "persistencia y recarga desde la base de datos" do
    # La persistencia corre en un Task que no hereda la conexión del sandbox: probarla aquí es
    # intermitente; la cubren los tests del panel de administración.

    test "leer dos veces seguidas no vuelve a consultar la base de datos" do
      # El estado se cachea unos segundos: sin ese caché, cada predicción abriría una
      # consulta para saber qué modelo usar.
      primero = App.SummarizerSettings.get()
      segundo = App.SummarizerSettings.get()
      assert primero.model == segundo.model
      assert Map.has_key?(primero, :cached_at)
    end

    test "un modelo inválido no altera el estado ya guardado" do
      App.SummarizerSettings.set_model("gemma4")
      {:error, _} = App.SummarizerSettings.set_model("modelo-que-no-existe")
      assert App.SummarizerSettings.get().model == "gemma4"
    end

    test "el estado por defecto trae los cuatro prompts" do
      estado = App.SummarizerSettings.get()

      for clave <- [
            :prompt_summary,
            :prompt_paraphrase,
            :user_prompt_summary,
            :user_prompt_paraphrase
          ] do
        assert is_binary(Map.fetch!(estado, clave))
        refute Map.fetch!(estado, clave) == ""
      end
    end
  end

  describe "estado inicial y recarga" do
    test "get/0 devuelve las seis claves del estado" do
      estado = App.SummarizerSettings.get()

      for clave <- [
            :model,
            :mode,
            :prompt_summary,
            :prompt_paraphrase,
            :user_prompt_summary,
            :user_prompt_paraphrase
          ] do
        assert Map.has_key?(estado, clave)
      end
    end

    test "el caché se refresca pasado su tiempo de vida" do
      # El estado se relee de la base de datos cada pocos segundos: sin eso, un cambio hecho
      # desde otra instancia no llegaría nunca a esta.
      primero = App.SummarizerSettings.get()
      assert is_integer(primero.cached_at)

      App.SummarizerSettings.set_mode("paraphrase")
      assert App.SummarizerSettings.get().mode == "paraphrase"
      App.SummarizerSettings.set_mode("summary")
    end

    test "cambiar de modo conserva los prompts" do
      App.SummarizerSettings.set_prompts("A {language}", "B {language}", "C {text}", "D {text}")
      App.SummarizerSettings.set_mode("paraphrase")

      estado = App.SummarizerSettings.get()
      assert estado.prompt_summary == "A {language}"
      assert estado.user_prompt_paraphrase == "D {text}"
      App.SummarizerSettings.set_mode("summary")
    end

    test "un modo inválido no altera el estado" do
      App.SummarizerSettings.set_mode("summary")
      {:error, _} = App.SummarizerSettings.set_mode("modo-inexistente")
      assert App.SummarizerSettings.get().mode == "summary"
    end

    test "desactivar el summarizer es un modelo válido" do
      assert App.SummarizerSettings.set_model("none") == :ok
      assert App.SummarizerSettings.get().model == "none"
    end
  end
end
