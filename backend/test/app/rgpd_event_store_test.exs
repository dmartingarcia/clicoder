defmodule App.RgpdEventStoreTest do
  @moduledoc """
  El informe clínico no puede acabar en el registro de eventos.

  Es una categoría especial del artículo 9 del RGPD y el registro es inmutable: lo que entra ahí
  no se puede borrar, de modo que guardarlo incumpliría el derecho de supresión del artículo 17
  que el sistema declara satisfacer. Estos tests fijan esa frontera, porque el fallo sería
  invisible: todo seguiría funcionando y el texto quedaría almacenado para siempre.
  """
  use App.DataCase

  alias App.Events.{AnalysisRequested, MessageSent}
  alias App.Projections.MessageProjection

  describe "los eventos no llevan el informe" do
    test "MessageSent no tiene campo de contenido" do
      refute Map.has_key?(%MessageSent{}, :content)
    end

    test "AnalysisRequested no tiene campo de texto del informe" do
      refute Map.has_key?(%AnalysisRequested{}, :report_text)
    end

    test "serializar un MessageSent completo no filtra texto clínico" do
      evento = %MessageSent{
        conversation_id: "c1",
        message_id: "m1",
        user_id: "u1",
        timestamp: DateTime.utc_now() |> DateTime.to_iso8601()
      }

      serializado = Jason.encode!(evento)

      # Lo que se guarda son identificadores y una marca temporal, nada más
      assert {:ok, campos} = Jason.decode(serializado)

      assert Map.keys(campos) |> Enum.sort() ==
               ["conversation_id", "message_id", "timestamp", "user_id"]
    end
  end

  describe "el texto vive solo donde se puede borrar" do
    test "la proyección de mensajes admite contenido nulo" do
      # Entre que el proyector crea la fila y el canal escribe el texto, la columna está vacía.
      # Si volviera a ser NOT NULL, el proyector fallaría y el mensaje no se registraría.
      assert %{content: nil} =
               MessageProjection.__struct__()
    end
  end
end
