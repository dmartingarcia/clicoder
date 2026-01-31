defmodule App.Commands.StartConversation do
  defstruct [:conversation_id, :user_id, :started_at]
end

defmodule App.Commands.SendMessage do
  defstruct [:conversation_id, :message_id, :user_id, :content, :timestamp]
end

defmodule App.Commands.AnalyzeReport do
  defstruct [:conversation_id, :message_id, :report_text]
end

defmodule App.Commands.ReceiveAIPrediction do
  defstruct [:conversation_id, :message_id, :predicted_codes, :reasoning, :confidence_scores]
end

defmodule App.Commands.ValidateCode do
  defstruct [:conversation_id, :code_id, :cie10_code, :validated_by, :validation_timestamp]
end

defmodule App.Commands.RejectCode do
  defstruct [:conversation_id, :code_id, :cie10_code, :rejection_reason, :rejected_by]
end
