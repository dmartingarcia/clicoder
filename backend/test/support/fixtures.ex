defmodule App.Fixtures do
  @moduledoc """
  Test data factories for users, conversations, messages, predicted codes,
  and analysis cards. Also provides helpers for generating valid JWT tokens
  using the same mechanism as AuthController/RequireAuth.
  """

  alias App.Repo
  alias App.Accounts.User

  alias App.Projections.{
    ConversationProjection,
    MessageProjection,
    PredictedCodeProjection,
    AnalysisCardProjection
  }

  @doc """
  Inserts a confirmed user into the database and returns the struct.

  Accepts an optional map of overrides. Defaults produce a unique, valid user.
  """
  def user_fixture(attrs \\ %{}) do
    unique = System.unique_integer([:positive])

    defaults = %{
      "first_name" => "Test",
      "last_name" => "User",
      "username" => "testuser#{unique}",
      "email" => "user#{unique}@example.com",
      "password" => "password123#{unique}",
      "locale" => "es"
    }

    attrs = Map.merge(defaults, attrs)

    {:ok, user} =
      %User{}
      |> User.registration_changeset(attrs)
      |> Ecto.Changeset.put_change(
        :confirmed_at,
        DateTime.utc_now() |> DateTime.truncate(:second)
      )
      |> Ecto.Changeset.put_change(:confirmation_token, nil)
      |> Repo.insert()

    user
  end

  @doc """
  Inserts an *unconfirmed* user (confirmation_token set, confirmed_at nil).
  """
  def unconfirmed_user_fixture(attrs \\ %{}) do
    unique = System.unique_integer([:positive])

    defaults = %{
      "first_name" => "Pending",
      "last_name" => "User",
      "username" => "pending#{unique}",
      "email" => "pending#{unique}@example.com",
      "password" => "password12345",
      "locale" => "es"
    }

    attrs = Map.merge(defaults, attrs)

    {:ok, user} =
      %User{}
      |> User.registration_changeset(attrs)
      |> Repo.insert()

    user
  end

  @doc """
  Generates a valid Phoenix.Token for the given user (or user_id).
  This mirrors exactly what AuthController.login/2 produces and what
  RequireAuth validates.
  """
  def generate_token(%User{id: id}), do: generate_token(id)

  def generate_token(user_id) do
    Phoenix.Token.sign(AppWeb.Endpoint, "user auth", user_id)
  end

  @doc """
  Returns `{"authorization", "Bearer <token>"}` ready to pass to
  `put_req_header/3`.
  """
  def auth_header(%User{} = user) do
    {"authorization", "Bearer #{generate_token(user)}"}
  end

  def auth_header(user_id) when is_binary(user_id) do
    {"authorization", "Bearer #{generate_token(user_id)}"}
  end

  @doc """
  Inserts an active ConversationProjection row directly via Repo.
  """
  def conversation_fixture(user, attrs \\ %{}) do
    conversation_id = UUID.uuid4()
    now = DateTime.utc_now() |> DateTime.truncate(:second)

    defaults = %{
      conversation_id: conversation_id,
      user_id: to_string(user.id),
      started_at: now,
      status: "active",
      deleted_at: nil
    }

    attrs = Map.merge(defaults, attrs)

    %ConversationProjection{}
    |> Ecto.Changeset.cast(attrs, [:conversation_id, :user_id, :started_at, :status, :deleted_at])
    |> Repo.insert!()
  end

  @doc """
  Inserts a soft-deleted (trashed) conversation.
  """
  def deleted_conversation_fixture(user, attrs \\ %{}) do
    now = DateTime.utc_now() |> DateTime.truncate(:second)
    conversation_fixture(user, Map.merge(%{deleted_at: now}, attrs))
  end

  @doc """
  Inserts a MessageProjection row belonging to the given conversation struct.
  """
  def message_fixture(conversation, attrs \\ %{}) do
    unique = System.unique_integer([:positive])
    now = DateTime.utc_now() |> DateTime.truncate(:second)

    defaults = %{
      message_id: UUID.uuid4(),
      content: "Message content #{unique}",
      user_id: conversation.user_id,
      timestamp: now,
      message_type: "user",
      conversation_id: conversation.id
    }

    attrs = Map.merge(defaults, attrs)

    %MessageProjection{}
    |> Ecto.Changeset.cast(attrs, [
      :message_id,
      :content,
      :user_id,
      :timestamp,
      :message_type,
      :conversation_id
    ])
    |> Repo.insert!()
  end

  @doc """
  Inserts a PredictedCodeProjection row belonging to the given conversation struct.
  """
  def predicted_code_fixture(conversation, attrs \\ %{}) do
    defaults = %{
      code_id: UUID.uuid4(),
      cie10_code: "J45.0",
      reasoning: "Asthma, predominantly allergic",
      confidence_score: 0.92,
      status: "pending",
      conversation_id: conversation.id
    }

    attrs = Map.merge(defaults, attrs)

    %PredictedCodeProjection{}
    |> Ecto.Changeset.cast(attrs, [
      :code_id,
      :cie10_code,
      :reasoning,
      :confidence_score,
      :status,
      :validated_by,
      :rejected_by,
      :rejection_reason,
      :conversation_id
    ])
    |> Repo.insert!()
  end

  @doc """
  Inserts an AnalysisCardProjection row belonging to the given conversation struct.
  """
  def analysis_card_fixture(conversation, attrs \\ %{}) do
    defaults = %{
      card_id: UUID.uuid4(),
      card_type: "summary",
      content: "Patient presents with respiratory symptoms.",
      position: 0,
      message_id: UUID.uuid4(),
      conversation_id: conversation.id
    }

    attrs = Map.merge(defaults, attrs)

    %AnalysisCardProjection{}
    |> Ecto.Changeset.cast(attrs, [
      :card_id,
      :card_type,
      :content,
      :position,
      :message_id,
      :conversation_id
    ])
    |> Repo.insert!()
  end
end
