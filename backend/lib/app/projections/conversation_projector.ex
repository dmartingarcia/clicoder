defmodule App.Projections.ConversationProjector do
  use Commanded.Projections.Ecto,
    application: App.CommandedApplication,
    repo: App.Repo,
    name: "ConversationProjector"

  alias App.Events.{
    ConversationStarted,
    MessageSent,
    AIPredictionReceived,
    CodeValidated,
    CodeRejected
  }

  alias App.Projections.{
    ConversationProjection,
    MessageProjection,
    PredictedCodeProjection
  }

  project(%ConversationStarted{} = evt, _metadata, fn multi ->
    {:ok, started_at, _} = DateTime.from_iso8601(evt.started_at)
    started_at = DateTime.truncate(started_at, :second)

    Ecto.Multi.insert(multi, :conversation, %ConversationProjection{
      conversation_id: evt.conversation_id,
      user_id: evt.user_id,
      started_at: started_at,
      status: "active"
    })
  end)

  project(%MessageSent{} = evt, _metadata, fn multi ->
    Ecto.Multi.run(multi, :message, fn repo, _changes ->
      {:ok, timestamp, _} = DateTime.from_iso8601(evt.timestamp)
      timestamp = DateTime.truncate(timestamp, :second)
      conversation = repo.get_by!(ConversationProjection, conversation_id: evt.conversation_id)

      # El evento ya no lleva el texto del informe, de modo que aqui solo se materializa el
      # hecho. El contenido lo escribe el canal directamente sobre esta misma fila, porque es
      # el unico sitio donde existe y porque asi desaparece al borrar la conversacion.
      message = %MessageProjection{
        message_id: evt.message_id,
        content: nil,
        user_id: evt.user_id,
        timestamp: timestamp,
        message_type: "user_message",
        conversation_id: conversation.id
      }

      repo.insert(message, on_conflict: :nothing, conflict_target: :message_id)
    end)
  end)

  # El canal escribe las tarjetas en cuanto llegan, porque la interfaz las va pintando segun
  # se reciben y el proyector es asincrono. Aqui volver a insertarlas las duplicaria, asi que
  # este evento cumple solo su otro cometido: dejar en el registro inmutable con que motor y
  # con que pesos se predijo cada informe, que es lo que exige la trazabilidad.
  project(%AIPredictionReceived{}, _metadata, fn multi -> multi end)

  project(%CodeValidated{} = evt, _metadata, fn multi ->
    Ecto.Multi.run(multi, :validate_code, fn repo, _changes ->
      conversation = repo.get_by!(ConversationProjection, conversation_id: evt.conversation_id)

      code =
        repo.get_by!(PredictedCodeProjection,
          code_id: evt.code_id,
          conversation_id: conversation.id
        )

      code
      |> PredictedCodeProjection.changeset(%{
        status: "validated",
        validated_by: evt.validated_by
      })
      |> repo.update()
    end)
  end)

  project(%CodeRejected{} = evt, _metadata, fn multi ->
    Ecto.Multi.run(multi, :reject_code, fn repo, _changes ->
      conversation = repo.get_by!(ConversationProjection, conversation_id: evt.conversation_id)

      code =
        repo.get_by!(PredictedCodeProjection,
          code_id: evt.code_id,
          conversation_id: conversation.id
        )

      code
      |> PredictedCodeProjection.changeset(%{
        status: "rejected",
        rejected_by: evt.rejected_by,
        rejection_reason: evt.rejection_reason
      })
      |> repo.update()
    end)
  end)

  @impl Commanded.Event.Handler
  def error({:error, reason}, event, _failure_context) do
    require Logger

    Logger.warning(
      "ConversationProjector skipping event #{inspect(event.__struct__)} due to: #{inspect(reason)}"
    )

    :skip
  end
end
