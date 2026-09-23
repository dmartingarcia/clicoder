defmodule App.SettingsTest do
  use App.DataCase, async: true

  alias App.Settings

  describe "load/0" do
    test "returns nil when no settings row exists" do
      assert Settings.load() == nil
    end
  end

  describe "save/1" do
    test "inserts a new row when none exists" do
      attrs = %{
        summarizer_model: "gemma3",
        summarizer_mode: "summary",
        prompt_summary: "System resumen",
        prompt_paraphrase: "System paráfrasis",
        user_prompt_summary: "User resumen {text}",
        user_prompt_paraphrase: "User paráfrasis {text}"
      }

      assert {:ok, saved} = Settings.save(attrs)
      assert saved.summarizer_model == "gemma3"
      assert saved.summarizer_mode == "summary"
      assert saved.prompt_summary == "System resumen"
    end

    test "updates the existing row on second save" do
      {:ok, _} =
        Settings.save(%{summarizer_model: "gemma3", summarizer_mode: "summary"})

      {:ok, updated} =
        Settings.save(%{summarizer_model: "phi4", summarizer_mode: "paraphrase"})

      assert updated.summarizer_model == "phi4"
      assert updated.summarizer_mode == "paraphrase"
      assert Settings.load().summarizer_model == "phi4"
    end

    test "load/0 returns the saved row after save/1" do
      {:ok, _} =
        Settings.save(%{summarizer_model: "qwen", summarizer_mode: "summary"})

      row = Settings.load()
      assert row.summarizer_model == "qwen"
    end
  end

  describe "método de explicabilidad" do
    test "se guarda y se relee" do
      # La fila exige modelo y modo del resumidor: sin ellos el insert no pasa la validacion.
      {:ok, _} =
        App.Settings.save(%{
          summarizer_model: "none",
          summarizer_mode: "summary",
          explain_method: "exhaustivo"
        })

      assert App.Settings.load().explain_method == "exhaustivo"
    end

    test "guardarlo no pisa los ajustes del resumidor" do
      {:ok, _} = App.Settings.save(%{summarizer_model: "gemma3", summarizer_mode: "summary"})
      {:ok, _} = App.Settings.save(%{explain_method: "divide_y_venceras"})

      guardado = App.Settings.load()
      assert guardado.explain_method == "divide_y_venceras"
      assert guardado.summarizer_model == "gemma3"
    end
  end
end
