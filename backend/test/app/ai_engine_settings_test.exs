defmodule App.AIEngineSettingsTest do
  use ExUnit.Case, async: false

  # The Agent is a named global process started by the application supervisor.
  # Each test resets it to the default value so tests don't interfere with
  # each other regardless of execution order.

  setup do
    App.AIEngineSettings.set_engine("bert")
    App.AIEngineSettings.set_explain_method("gradiente_filtrado")
    :ok
  end

  describe "get_engine/0" do
    test "returns 'bert' by default" do
      assert App.AIEngineSettings.get_engine() == "bert"
    end
  end

  describe "set_engine/1" do
    test "sets engine to 'dict' and get_engine/0 reflects the change" do
      :ok = App.AIEngineSettings.set_engine("dict")
      assert App.AIEngineSettings.get_engine() == "dict"
    end

    test "sets engine to 'both' and returns :ok" do
      assert App.AIEngineSettings.set_engine("both") == :ok
      assert App.AIEngineSettings.get_engine() == "both"
    end

    test "returns {:error, ...} for an invalid engine name" do
      assert App.AIEngineSettings.set_engine("invalid") ==
               {:error, "Motor inválido: invalid"}
    end

    test "returns {:error, ...} for an empty string" do
      assert {:error, "Motor inválido: " <> _} = App.AIEngineSettings.set_engine("")
    end

    test "acepta el motor fusionado" do
      assert App.AIEngineSettings.set_engine("fused") == :ok
      assert App.AIEngineSettings.get_engine() == "fused"
    end
  end

  describe "explain_method" do
    test "por defecto usa la estrategia recomendada" do
      assert App.AIEngineSettings.get_explain_method() == "gradiente_filtrado"
    end

    test "acepta las cuatro estrategias" do
      for metodo <- ~w(diccionario gradiente_filtrado exhaustivo divide_y_venceras) do
        assert App.AIEngineSettings.set_explain_method(metodo) == :ok
        assert App.AIEngineSettings.get_explain_method() == metodo
      end
    end

    test "rechaza una estrategia desconocida" do
      assert App.AIEngineSettings.set_explain_method("magia") ==
               {:error, "Método inválido: magia"}
    end

    test "cambiar la estrategia no altera el motor" do
      :ok = App.AIEngineSettings.set_engine("fused")
      :ok = App.AIEngineSettings.set_explain_method("exhaustivo")
      assert App.AIEngineSettings.get_engine() == "fused"
    end
  end
end
