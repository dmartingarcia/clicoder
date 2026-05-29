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
    PredictedCodeProjection,
    AnalysisCardProjection
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

      # Guardar tarjetas de análisis
      evt.cards
      |> Enum.with_index()
      |> Enum.each(fn {card, idx} ->
        card_type = card[:type] || card["type"]
        card_content = card[:content] || card["content"]

        content =
          case card_type do
            "codes" -> Jason.encode!(card_content)
            _ -> card_content
          end

        %AnalysisCardProjection{
          card_id: UUID.uuid4(),
          card_type: card_type,
          content: content,
          position: idx,
          message_id: evt.message_id,
          conversation_id: conversation.id,
          engine: evt.engine
        }
        |> repo.insert()
      end)

      {:ok, nil}
    end)
  end)

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
