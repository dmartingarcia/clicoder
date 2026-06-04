defmodule App.Projections.ConversationProjection do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, :binary_id, autogenerate: true}
  @foreign_key_type :binary_id

  schema "conversations" do
    field :conversation_id, :string
    field :user_id, :string
    field :started_at, :utc_datetime
    field :status, :string, default: "active"
    field :deleted_at, :utc_datetime

    has_many :messages, App.Projections.MessageProjection, foreign_key: :conversation_id

    has_many :predicted_codes, App.Projections.PredictedCodeProjection,
      foreign_key: :conversation_id

    has_many :analysis_cards, App.Projections.AnalysisCardProjection,
      foreign_key: :conversation_id

    timestamps(type: :utc_datetime)
  end

  def changeset(projection, attrs) do
    projection
    |> cast(attrs, [:conversation_id, :user_id, :started_at, :status])
    |> validate_required([:conversation_id, :user_id, :started_at])
    |> unique_constraint(:conversation_id)
  end
end

defmodule App.Projections.MessageProjection do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, :binary_id, autogenerate: true}
  @foreign_key_type :binary_id

  schema "messages" do
    field :message_id, :string
    field :content, :string
    field :user_id, :string
    field :timestamp, :utc_datetime
    field :message_type, :string

    belongs_to :conversation, App.Projections.ConversationProjection

    timestamps(type: :utc_datetime)
  end

  def changeset(projection, attrs) do
    projection
    |> cast(attrs, [:message_id, :content, :user_id, :timestamp, :message_type, :conversation_id])
    |> validate_required([:message_id, :content, :timestamp, :conversation_id])
  end
end

defmodule App.Projections.AnalysisCardProjection do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, :binary_id, autogenerate: true}
  @foreign_key_type :binary_id

  schema "analysis_cards" do
    field :card_id, :string
    field :card_type, :string
    field :content, :string
    field :position, :integer
    field :message_id, :string
    field :engine, :string

    belongs_to :conversation, App.Projections.ConversationProjection

    timestamps(type: :utc_datetime)
  end

  def changeset(card, attrs) do
    card
    |> cast(attrs, [
      :card_id,
      :card_type,
      :content,
      :position,
      :message_id,
      :conversation_id,
      :engine
    ])
    |> validate_required([:card_id, :card_type, :content, :conversation_id])
  end
end

defmodule App.Projections.PredictedCodeProjection do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, :binary_id, autogenerate: true}
  @foreign_key_type :binary_id

  schema "predicted_codes" do
    field :code_id, :string
    field :cie10_code, :string
    field :reasoning, :string
    field :confidence_score, :float
    field :status, :string
    field :validated_by, :string
    field :rejected_by, :string
    field :rejection_reason, :string
    field :verified_triggers, {:array, :string}, default: []

    belongs_to :conversation, App.Projections.ConversationProjection

    timestamps(type: :utc_datetime)
  end

  def changeset(projection, attrs) do
    projection
    |> cast(attrs, [
      :code_id,
      :cie10_code,
      :reasoning,
      :confidence_score,
      :status,
      :validated_by,
      :rejected_by,
      :rejection_reason,
      :verified_triggers,
      :conversation_id
    ])
    |> validate_required([:cie10_code, :conversation_id])
  end
end

defmodule App.Projections.CodeSuggestionProjection do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, :binary_id, autogenerate: true}
  @foreign_key_type :binary_id

  schema "code_suggestions" do
    field :suggestion_id, :string
    field :selected_text, :string
    field :suggested_code, :string
    field :suggested_by, :string

    belongs_to :conversation, App.Projections.ConversationProjection

    timestamps(type: :utc_datetime)
  end

  def changeset(suggestion, attrs) do
    suggestion
    |> cast(attrs, [
      :suggestion_id,
      :selected_text,
      :suggested_code,
      :suggested_by,
      :conversation_id
    ])
    |> validate_required([
      :suggestion_id,
      :selected_text,
      :suggested_code,
      :suggested_by,
      :conversation_id
    ])
    |> unique_constraint(:suggestion_id)
  end
end
