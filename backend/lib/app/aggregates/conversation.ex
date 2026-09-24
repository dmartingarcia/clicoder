defmodule App.Aggregates.Conversation do
  @moduledoc """
  Aggregate: Conversación de chatbot médico con Event Sourcing
  """
  defstruct [
    :conversation_id,
    :user_id,
    :started_at,
    messages: [],
    pending_analysis: false,
    validated_codes: [],
    rejected_codes: []
  ]

  alias App.Aggregates.Conversation

  alias App.Commands.{
    StartConversation,
    SendMessage,
    AnalyzeReport,
    ReceiveAIPrediction,
    ValidateCode,
    RejectCode
  }

  alias App.Events.{
    ConversationStarted,
    MessageSent,
    AnalysisRequested,
    AIPredictionReceived,
    CodeValidated,
    CodeRejected
  }

  # Command Handlers
  def execute(%Conversation{conversation_id: nil}, %StartConversation{} = cmd) do
    %ConversationStarted{
      conversation_id: cmd.conversation_id,
      user_id: cmd.user_id,
      started_at: cmd.started_at
    }
  end

  def execute(%Conversation{conversation_id: nil}, _cmd), do: {:error, :conversation_not_started}

  def execute(%Conversation{}, %SendMessage{} = cmd) do
    %MessageSent{
      conversation_id: cmd.conversation_id,
      message_id: cmd.message_id,
      user_id: cmd.user_id,
      timestamp: cmd.timestamp
    }
  end

  def execute(%Conversation{pending_analysis: true}, %AnalyzeReport{}),
    do: {:error, :analysis_in_progress}

  def execute(%Conversation{}, %AnalyzeReport{} = cmd) do
    %AnalysisRequested{
      conversation_id: cmd.conversation_id,
      message_id: cmd.message_id,
      requested_at: DateTime.utc_now()
    }
  end

  def execute(%Conversation{}, %ReceiveAIPrediction{} = cmd) do
    %AIPredictionReceived{
      conversation_id: cmd.conversation_id,
      message_id: cmd.message_id,
      cards: cmd.cards,
      predicted_codes: cmd.predicted_codes,
      reasoning: cmd.reasoning,
      confidence_scores: cmd.confidence_scores,
      received_at: DateTime.utc_now(),
      engine: cmd.engine,
      model_version: cmd.model_version
    }
  end

  def execute(%Conversation{} = conv, %ValidateCode{} = cmd) do
    cond do
      cmd.cie10_code in conv.validated_codes ->
        {:error, :code_already_validated}

      cmd.cie10_code in conv.rejected_codes ->
        {:error, :code_was_rejected}

      true ->
        %CodeValidated{
          conversation_id: cmd.conversation_id,
          code_id: cmd.code_id,
          cie10_code: cmd.cie10_code,
          validated_by: cmd.validated_by,
          validation_timestamp: cmd.validation_timestamp
        }
    end
  end

  def execute(%Conversation{} = conv, %RejectCode{} = cmd) do
    if cmd.cie10_code in conv.validated_codes do
      {:error, :cannot_reject_validated_code}
    else
      %CodeRejected{
        conversation_id: cmd.conversation_id,
        code_id: cmd.code_id,
        cie10_code: cmd.cie10_code,
        rejection_reason: cmd.rejection_reason,
        rejected_by: cmd.rejected_by,
        rejected_at: DateTime.utc_now()
      }
    end
  end

  # Event Handlers (State Evolution)
  def apply(%Conversation{} = conv, %ConversationStarted{} = evt) do
    %Conversation{
      conv
      | conversation_id: evt.conversation_id,
        user_id: evt.user_id,
        started_at: evt.started_at
    }
  end

  def apply(%Conversation{} = conv, %MessageSent{} = evt) do
    message = %{
      message_id: evt.message_id,
      user_id: evt.user_id,
      timestamp: evt.timestamp
    }

    %Conversation{conv | messages: conv.messages ++ [message]}
  end

  def apply(%Conversation{} = conv, %AnalysisRequested{}),
    do: %Conversation{conv | pending_analysis: true}

  def apply(%Conversation{} = conv, %AIPredictionReceived{}),
    do: %Conversation{conv | pending_analysis: false}

  def apply(%Conversation{} = conv, %CodeValidated{} = evt) do
    %Conversation{conv | validated_codes: conv.validated_codes ++ [evt.cie10_code]}
  end

  def apply(%Conversation{} = conv, %CodeRejected{} = evt) do
    %Conversation{conv | rejected_codes: conv.rejected_codes ++ [evt.cie10_code]}
  end
end
