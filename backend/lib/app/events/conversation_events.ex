defmodule App.Events.ConversationStarted do
  @derive Jason.Encoder
  defstruct [:conversation_id, :user_id, :started_at]
end

defmodule App.Events.MessageSent do
  @derive Jason.Encoder
  # Sin :content a proposito: el informe es dato del art. 9 RGPD y el registro de eventos es
  # inmutable; el texto vive solo en la proyeccion, que si se puede suprimir.
  defstruct [:conversation_id, :message_id, :user_id, :timestamp]
end

defmodule App.Events.AnalysisRequested do
  @derive Jason.Encoder
  # Sin :report_text, por la misma razon que MessageSent.
  defstruct [:conversation_id, :message_id, :requested_at]
end

defmodule App.Events.AIPredictionReceived do
  @derive Jason.Encoder
  defstruct [
    :conversation_id,
    :message_id,
    :cards,
    :predicted_codes,
    :reasoning,
    :confidence_scores,
    :received_at,
    :engine,
    :model_version
  ]
end

# Solo registran los atomos en compilacion: EventStore reproduce con Jason keys: :atoms!
# y necesita conocer todas las claves, incluidas las anidadas en :cards y :predicted_codes.
defmodule App.Events.CardData do
  @derive Jason.Encoder
  defstruct [:type, :content, :card_type, :card_id, :position]
end

defmodule App.Events.CodeData do
  @derive Jason.Encoder
  defstruct [:code, :description, :reason, :reasoning, :confidence, :status, :code_id]
end

defmodule App.Events.CodeValidated do
  @derive Jason.Encoder
  defstruct [:conversation_id, :code_id, :cie10_code, :validated_by, :validation_timestamp]
end

defmodule App.Events.CodeRejected do
  @derive Jason.Encoder
  defstruct [
    :conversation_id,
    :code_id,
    :cie10_code,
    :rejection_reason,
    :rejected_by,
    :rejected_at
  ]
end
