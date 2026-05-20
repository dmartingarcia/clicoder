defmodule App.Projections.ConversationProjectorTest do
  @moduledoc """
  Tests for the projection schemas and the DB operations that
  ConversationProjector performs. We test those operations directly via Repo
  rather than going through the Commanded event bus (which requires
  EventStore infra not available in the test sandbox).
  """

  use App.DataCase, async: true

  import Ecto.Query

  alias App.Repo

  alias App.Projections.{
    ConversationProjection,
    MessageProjection,
    PredictedCodeProjection,
    AnalysisCardProjection
  }

  # ---------------------------------------------------------------------------
  # Helpers
  # ---------------------------------------------------------------------------

  defp insert_conversation(attrs \\ %{}) do
    defaults = %{
      conversation_id: UUID.uuid4(),
      user_id: UUID.uuid4(),
      started_at: DateTime.utc_now() |> DateTime.truncate(:second),
      status: "active"
    }

    %ConversationProjection{}
    |> Ecto.Changeset.cast(Map.merge(defaults, attrs), [
      :conversation_id,
      :user_id,
      :started_at,
      :status,
      :deleted_at
    ])
    |> Repo.insert!()
  end

  defp insert_predicted_code(conv, attrs \\ %{}) do
    defaults = %{
      code_id: UUID.uuid4(),
      cie10_code: "J45.0",
      reasoning: "Asthma",
      confidence_score: 0.85,
      status: "pending",
      conversation_id: conv.id
    }

    %PredictedCodeProjection{}
    |> Ecto.Changeset.cast(Map.merge(defaults, attrs), [
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

  # ---------------------------------------------------------------------------
  # ConversationProjection schema
  # ---------------------------------------------------------------------------

  describe "ConversationProjection schema" do
    test "inserts with required fields" do
      conv = insert_conversation()

      assert conv.status == "active"
      assert conv.deleted_at == nil
      assert is_binary(conv.conversation_id)
    end

    test "started_at is persisted correctly" do
      dt = ~U[2024-06-15 10:30:00Z]
      conv = insert_conversation(%{started_at: dt})
      assert conv.started_at == dt
    end

    test "changeset rejects missing conversation_id" do
      cs =
        %ConversationProjection{}
        |> ConversationProjection.changeset(%{
          user_id: UUID.uuid4(),
          started_at: DateTime.utc_now()
        })

      assert %{conversation_id: _} = errors_on(cs)
    end

    test "changeset rejects missing user_id" do
      cs =
        %ConversationProjection{}
        |> ConversationProjection.changeset(%{
          conversation_id: UUID.uuid4(),
          started_at: DateTime.utc_now()
        })

      assert %{user_id: _} = errors_on(cs)
    end

    test "soft-delete: deleted_at can be set" do
      conv = insert_conversation()
      now = DateTime.utc_now() |> DateTime.truncate(:second)

      {:ok, updated} =
        conv
        |> Ecto.Changeset.cast(%{deleted_at: now}, [:deleted_at])
        |> Repo.update()

      assert updated.deleted_at == now
    end
  end

  # ---------------------------------------------------------------------------
  # MessageProjection schema
  # ---------------------------------------------------------------------------

  describe "MessageProjection schema" do
    setup do
      %{conv: insert_conversation()}
    end

    test "inserts message with required fields", %{conv: conv} do
      msg_id = UUID.uuid4()
      now = DateTime.utc_now() |> DateTime.truncate(:second)

      msg =
        %MessageProjection{}
        |> Ecto.Changeset.cast(
          %{
            message_id: msg_id,
            content: "Paciente con hipertensión",
            user_id: conv.user_id,
            timestamp: now,
            message_type: "user_message",
            conversation_id: conv.id
          },
          [:message_id, :content, :user_id, :timestamp, :message_type, :conversation_id]
        )
        |> Repo.insert!()

      assert msg.message_id == msg_id
      assert msg.content == "Paciente con hipertensión"
      assert msg.conversation_id == conv.id
    end

    test "multiple messages can belong to the same conversation", %{conv: conv} do
      now = DateTime.utc_now() |> DateTime.truncate(:second)

      for i <- 1..3 do
        %MessageProjection{}
        |> Ecto.Changeset.cast(
          %{
            message_id: UUID.uuid4(),
            content: "Mensaje #{i}",
            user_id: conv.user_id,
            timestamp: now,
            message_type: "user_message",
            conversation_id: conv.id
          },
          [:message_id, :content, :user_id, :timestamp, :message_type, :conversation_id]
        )
        |> Repo.insert!()
      end

      count =
        MessageProjection
        |> where([m], m.conversation_id == ^conv.id)
        |> Repo.aggregate(:count)

      assert count == 3
    end
  end

  # ---------------------------------------------------------------------------
  # PredictedCodeProjection schema
  # ---------------------------------------------------------------------------

  describe "PredictedCodeProjection schema" do
    setup do
      %{conv: insert_conversation()}
    end

    test "inserts pending code", %{conv: conv} do
      code = insert_predicted_code(conv, %{cie10_code: "I10", reasoning: "Hypertension"})

      assert code.cie10_code == "I10"
      assert code.status == "pending"
      assert code.validated_by == nil
      assert code.rejected_by == nil
    end

    test "validates to 'validated' status with validated_by", %{conv: conv} do
      code = insert_predicted_code(conv)
      user_id = UUID.uuid4()

      {:ok, updated} =
        code
        |> PredictedCodeProjection.changeset(%{status: "validated", validated_by: user_id})
        |> Repo.update()

      assert updated.status == "validated"
      assert updated.validated_by == user_id
    end

    test "rejects to 'rejected' status with reason and rejected_by", %{conv: conv} do
      code = insert_predicted_code(conv)
      user_id = UUID.uuid4()

      {:ok, updated} =
        code
        |> PredictedCodeProjection.changeset(%{
          status: "rejected",
          rejected_by: user_id,
          rejection_reason: "wrong diagnosis"
        })
        |> Repo.update()

      assert updated.status == "rejected"
      assert updated.rejected_by == user_id
      assert updated.rejection_reason == "wrong diagnosis"
    end

    test "multiple codes can belong to the same conversation", %{conv: conv} do
      for code <- ["I10", "E11", "J45.0"] do
        insert_predicted_code(conv, %{cie10_code: code, code_id: UUID.uuid4()})
      end

      codes =
        PredictedCodeProjection
        |> where([c], c.conversation_id == ^conv.id)
        |> select([c], c.cie10_code)
        |> Repo.all()
        |> Enum.sort()

      assert codes == ["E11", "I10", "J45.0"]
    end
  end

  # ---------------------------------------------------------------------------
  # AnalysisCardProjection schema
  # ---------------------------------------------------------------------------

  describe "AnalysisCardProjection schema" do
    setup do
      %{conv: insert_conversation()}
    end

    test "inserts card with required fields", %{conv: conv} do
      card_id = UUID.uuid4()

      card =
        %AnalysisCardProjection{}
        |> Ecto.Changeset.cast(
          %{
            card_id: card_id,
            card_type: "summary",
            content: "Analysis summary text",
            position: 0,
            message_id: UUID.uuid4(),
            conversation_id: conv.id
          },
          [:card_id, :card_type, :content, :position, :message_id, :conversation_id]
        )
        |> Repo.insert!()

      assert card.card_id == card_id
      assert card.card_type == "summary"
      assert card.position == 0
    end

    test "cards are retrieved in position order", %{conv: conv} do
      msg_id = UUID.uuid4()

      for {type, pos} <- [{"recommendations", 2}, {"summary", 0}, {"codes", 1}] do
        %AnalysisCardProjection{}
        |> Ecto.Changeset.cast(
          %{
            card_id: UUID.uuid4(),
            card_type: type,
            content: "content",
            position: pos,
            message_id: msg_id,
            conversation_id: conv.id
          },
          [:card_id, :card_type, :content, :position, :message_id, :conversation_id]
        )
        |> Repo.insert!()
      end

      types =
        AnalysisCardProjection
        |> where([c], c.conversation_id == ^conv.id)
        |> order_by([c], c.position)
        |> select([c], c.card_type)
        |> Repo.all()

      assert types == ["summary", "codes", "recommendations"]
    end

    test "codes card content is valid JSON", %{conv: conv} do
      codes_json = Jason.encode!([%{code: "I10", confidence: 0.9}])

      card =
        %AnalysisCardProjection{}
        |> Ecto.Changeset.cast(
          %{
            card_id: UUID.uuid4(),
            card_type: "codes",
            content: codes_json,
            position: 0,
            message_id: UUID.uuid4(),
            conversation_id: conv.id
          },
          [:card_id, :card_type, :content, :position, :message_id, :conversation_id]
        )
        |> Repo.insert!()

      assert {:ok, decoded} = Jason.decode(card.content)
      assert [%{"code" => "I10"}] = decoded
    end
  end
end
