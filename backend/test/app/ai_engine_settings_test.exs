defmodule App.AIEngineSettingsTest do
  use ExUnit.Case, async: false

  # The Agent is a named global process started by the application supervisor.
  # Each test resets it to the default value so tests don't interfere with
  # each other regardless of execution order.

  setup do
    App.AIEngineSettings.set_engine("bert")
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
  end
end
