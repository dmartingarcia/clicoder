defmodule App.Router do
  @moduledoc """
  Commanded Router: Mapea comandos a Aggregates
  """
  use Commanded.Commands.Router

  alias App.Aggregates.Conversation
  alias App.Commands.{
    StartConversation,
    SendMessage,
    AnalyzeReport,
    ReceiveAIPrediction,
    ValidateCode,
    RejectCode
  }

  identify(Conversation, by: :conversation_id, prefix: "conversation-")

  dispatch([
    StartConversation,
    SendMessage,
    AnalyzeReport,
    ReceiveAIPrediction,
    ValidateCode,
    RejectCode
  ], to: Conversation)
end
