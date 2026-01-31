defmodule App.Projections.ConversationProjector do
  use Commanded.Projections.Ecto,
    application: App.CommandedApplication,
    repo: App.Repo,
    name: "ConversationProjector"

  alias App.Events.{ConversationStarted, MessageSent, AIPredictionReceived, CodeValidated, CodeRejected}
  alias App.Projections.{ConversationProjection, MessageProjection, PredictedCodeProjection}

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

      message = %MessageProjection{
        message_id: evt.message_id,
        content: evt.content,
        user_id: evt.user_id,
        timestamp: timestamp,
        message_type: "user_message",
        conversation_id: conversation.id
      }

      repo.insert(message)
    end)
  end)

  project(%AIPredictionReceived{} = evt, _metadata, fn multi ->
    Ecto.Multi.run(multi, :ai_prediction, fn repo, _changes ->
      conversation = repo.get_by!(ConversationProjection, conversation_id: evt.conversation_id)

      # Guardar códigos predichos
      Enum.each(evt.predicted_codes, fn code_data ->
        %PredictedCodeProjection{
          code_id: UUID.uuid4(),
          cie10_code: code_data[:code] || code_data["code"],
          reasoning: code_data[:reasoning] || code_data["reasoning"],
          confidence_score: code_data[:confidence] || code_data["confidence"],
          status: "pending",
          conversation_id: conversation.id
        }
        |> repo.insert()
      end)

      {:ok, nil}
    end)
  end)

  project(%CodeValidated{} = evt, _metadata, fn multi ->
    Ecto.Multi.run(multi, :validate_code, fn repo, _changes ->
      conversation = repo.get_by!(ConversationProjection, conversation_id: evt.conversation_id)
      code = repo.get_by!(PredictedCodeProjection, code_id: evt.code_id, conversation_id: conversation.id)

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
      code = repo.get_by!(PredictedCodeProjection, code_id: evt.code_id, conversation_id: conversation.id)

      code
      |> PredictedCodeProjection.changeset(%{
        status: "rejected",
        rejected_by: evt.rejected_by,
        rejection_reason: evt.rejection_reason
      })
      |> repo.update()
    end)
  end)
end
