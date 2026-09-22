defmodule App.Aggregates.ConversationTest do
  use ExUnit.Case, async: true

  alias App.Aggregates.Conversation

  alias App.Commands.{
    StartConversation,
    SendMessage,
    AnalyzeReport,
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

  @conversation_id "conv-123"
  @user_id "user-456"
  @now DateTime.utc_now()

  defp new_conversation, do: %Conversation{}

  defp started_conversation do
    conv = new_conversation()

    event =
      Conversation.execute(conv, %StartConversation{
        conversation_id: @conversation_id,
        user_id: @user_id,
        started_at: @now
      })

    Conversation.apply(conv, event)
  end

  # ---------------------------------------------------------------------------
  # StartConversation
  # ---------------------------------------------------------------------------

  describe "execute StartConversation" do
    test "emits ConversationStarted from a new aggregate" do
      cmd = %StartConversation{
        conversation_id: @conversation_id,
        user_id: @user_id,
        started_at: @now
      }

      assert %ConversationStarted{conversation_id: @conversation_id, user_id: @user_id} =
               Conversation.execute(new_conversation(), cmd)
    end

    test "returns error when conversation already started" do
      assert {:error, :conversation_not_started} =
               Conversation.execute(new_conversation(), %SendMessage{})
    end
  end

  describe "apply ConversationStarted" do
    test "sets conversation_id and user_id" do
      event = %ConversationStarted{
        conversation_id: @conversation_id,
        user_id: @user_id,
        started_at: @now
      }

      conv = Conversation.apply(new_conversation(), event)
      assert conv.conversation_id == @conversation_id
      assert conv.user_id == @user_id
      assert conv.started_at == @now
    end
  end

  # ---------------------------------------------------------------------------
  # SendMessage
  # ---------------------------------------------------------------------------

  describe "execute SendMessage" do
    test "emits MessageSent" do
      cmd = %SendMessage{
        conversation_id: @conversation_id,
        message_id: "msg-1",
        user_id: @user_id,
        content: "Hello",
        timestamp: @now
      }

      assert %MessageSent{message_id: "msg-1", content: "Hello"} =
               Conversation.execute(started_conversation(), cmd)
    end
  end

  describe "apply MessageSent" do
    test "appends message to messages list" do
      conv = started_conversation()

      event = %MessageSent{
        conversation_id: @conversation_id,
        message_id: "msg-1",
        user_id: @user_id,
        content: "Hello",
        timestamp: @now
      }

      updated = Conversation.apply(conv, event)
      assert length(updated.messages) == 1
      assert hd(updated.messages).message_id == "msg-1"
    end

    test "accumulates multiple messages" do
      conv = started_conversation()

      conv =
        Conversation.apply(conv, %MessageSent{
          message_id: "m1",
          user_id: @user_id,
          content: "A",
          timestamp: @now,
          conversation_id: @conversation_id
        })

      conv =
        Conversation.apply(conv, %MessageSent{
          message_id: "m2",
          user_id: @user_id,
          content: "B",
          timestamp: @now,
          conversation_id: @conversation_id
        })

      assert length(conv.messages) == 2
    end
  end

  # ---------------------------------------------------------------------------
  # AnalyzeReport
  # ---------------------------------------------------------------------------

  describe "execute AnalyzeReport" do
    test "emits AnalysisRequested when no analysis pending" do
      cmd = %AnalyzeReport{
        conversation_id: @conversation_id,
        message_id: "msg-1",
        report_text: "Report"
      }

      assert %AnalysisRequested{} = Conversation.execute(started_conversation(), cmd)
    end

    test "returns error when analysis already in progress" do
      conv = started_conversation()

      event = %AnalysisRequested{
        conversation_id: @conversation_id,
        message_id: "m1",
        report_text: "R",
        requested_at: @now
      }

      conv_with_pending = Conversation.apply(conv, event)
      assert conv_with_pending.pending_analysis == true

      cmd = %AnalyzeReport{conversation_id: @conversation_id, message_id: "m2", report_text: "R2"}
      assert {:error, :analysis_in_progress} = Conversation.execute(conv_with_pending, cmd)
    end
  end

  describe "apply AnalysisRequested / AIPredictionReceived" do
    test "sets pending_analysis to true on AnalysisRequested" do
      conv = started_conversation()

      event = %AnalysisRequested{
        conversation_id: @conversation_id,
        message_id: "m",
        report_text: "R",
        requested_at: @now
      }

      assert Conversation.apply(conv, event).pending_analysis == true
    end

    test "clears pending_analysis on AIPredictionReceived" do
      conv = started_conversation()

      event_req = %AnalysisRequested{
        conversation_id: @conversation_id,
        message_id: "m",
        report_text: "R",
        requested_at: @now
      }

      conv = Conversation.apply(conv, event_req)

      event_pred = %AIPredictionReceived{
        conversation_id: @conversation_id,
        message_id: "m",
        cards: [],
        predicted_codes: [],
        reasoning: "",
        confidence_scores: [],
        received_at: @now
      }

      assert Conversation.apply(conv, event_pred).pending_analysis == false
    end
  end

  # ---------------------------------------------------------------------------
  # ValidateCode
  # ---------------------------------------------------------------------------

  describe "execute ValidateCode" do
    test "emits CodeValidated for a new code" do
      cmd = %ValidateCode{
        conversation_id: @conversation_id,
        code_id: "c1",
        cie10_code: "J45.0",
        validated_by: @user_id,
        validation_timestamp: @now
      }

      assert %CodeValidated{cie10_code: "J45.0"} =
               Conversation.execute(started_conversation(), cmd)
    end

    test "returns error when code already validated" do
      conv = started_conversation()

      event = %CodeValidated{
        conversation_id: @conversation_id,
        code_id: "c1",
        cie10_code: "J45.0",
        validated_by: @user_id,
        validation_timestamp: @now
      }

      conv = Conversation.apply(conv, event)

      cmd = %ValidateCode{
        conversation_id: @conversation_id,
        code_id: "c2",
        cie10_code: "J45.0",
        validated_by: @user_id,
        validation_timestamp: @now
      }

      assert {:error, :code_already_validated} = Conversation.execute(conv, cmd)
    end

    test "returns error when code was previously rejected" do
      conv = started_conversation()

      event = %CodeRejected{
        conversation_id: @conversation_id,
        code_id: "c1",
        cie10_code: "J45.0",
        rejection_reason: "wrong",
        rejected_by: @user_id,
        rejected_at: @now
      }

      conv = Conversation.apply(conv, event)

      cmd = %ValidateCode{
        conversation_id: @conversation_id,
        code_id: "c2",
        cie10_code: "J45.0",
        validated_by: @user_id,
        validation_timestamp: @now
      }

      assert {:error, :code_was_rejected} = Conversation.execute(conv, cmd)
    end
  end

  describe "apply CodeValidated" do
    test "adds code to validated_codes" do
      conv = started_conversation()

      event = %CodeValidated{
        conversation_id: @conversation_id,
        code_id: "c1",
        cie10_code: "J45.0",
        validated_by: @user_id,
        validation_timestamp: @now
      }

      updated = Conversation.apply(conv, event)
      assert "J45.0" in updated.validated_codes
    end
  end

  # ---------------------------------------------------------------------------
  # RejectCode
  # ---------------------------------------------------------------------------

  describe "execute RejectCode" do
    test "emits CodeRejected for a new code" do
      cmd = %RejectCode{
        conversation_id: @conversation_id,
        code_id: "c1",
        cie10_code: "J45.0",
        rejection_reason: "incorrect",
        rejected_by: @user_id
      }

      assert %CodeRejected{cie10_code: "J45.0"} =
               Conversation.execute(started_conversation(), cmd)
    end

    test "returns error when trying to reject a validated code" do
      conv = started_conversation()

      event = %CodeValidated{
        conversation_id: @conversation_id,
        code_id: "c1",
        cie10_code: "J45.0",
        validated_by: @user_id,
        validation_timestamp: @now
      }

      conv = Conversation.apply(conv, event)

      cmd = %RejectCode{
        conversation_id: @conversation_id,
        code_id: "c2",
        cie10_code: "J45.0",
        rejection_reason: "wrong",
        rejected_by: @user_id
      }

      assert {:error, :cannot_reject_validated_code} = Conversation.execute(conv, cmd)
    end
  end

  describe "apply CodeRejected" do
    test "adds code to rejected_codes" do
      conv = started_conversation()

      event = %CodeRejected{
        conversation_id: @conversation_id,
        code_id: "c1",
        cie10_code: "J45.0",
        rejection_reason: "wrong",
        rejected_by: @user_id,
        rejected_at: @now
      }

      updated = Conversation.apply(conv, event)
      assert "J45.0" in updated.rejected_codes
    end
  end

  describe "reconstrucción del estado a partir de los eventos" do
    # El agregado se reconstruye reproduciendo su historial: si un `apply` pierde un dato,
    # las decisiones posteriores se toman sobre un estado que no corresponde a lo ocurrido.
    test "rechazar un código lo añade a la lista de rechazados" do
      conv =
        %Conversation{conversation_id: "c1"}
        |> Conversation.apply(%CodeRejected{
          conversation_id: "c1",
          code_id: "x",
          cie10_code: "I10",
          rejection_reason: "no procede",
          rejected_by: "codificador",
          rejected_at: DateTime.utc_now()
        })

      assert "I10" in conv.rejected_codes
    end

    test "validar un código lo añade a la lista de validados" do
      conv =
        %Conversation{conversation_id: "c1"}
        |> Conversation.apply(%CodeValidated{
          conversation_id: "c1",
          code_id: "x",
          cie10_code: "E11.9",
          validated_by: "codificador",
          validation_timestamp: DateTime.utc_now()
        })

      assert "E11.9" in conv.validated_codes
    end

    test "recibir la predicción cierra el análisis pendiente" do
      conv =
        %Conversation{conversation_id: "c1", pending_analysis: true}
        |> Conversation.apply(%AIPredictionReceived{conversation_id: "c1"})

      refute conv.pending_analysis
    end

    test "pedir un análisis lo marca como pendiente" do
      conv =
        %Conversation{conversation_id: "c1"}
        |> Conversation.apply(%AnalysisRequested{conversation_id: "c1"})

      assert conv.pending_analysis
    end

    test "un mensaje queda registrado en el agregado" do
      conv =
        %Conversation{conversation_id: "c1"}
        |> Conversation.apply(%MessageSent{
          conversation_id: "c1",
          message_id: "m1",
          user_id: "u1",
          content: "informe",
          timestamp: DateTime.utc_now()
        })

      assert [%{message_id: "m1", content: "informe"}] = conv.messages
    end
  end

  describe "rechazo de un código ya validado" do
    test "no se puede rechazar lo que ya se validó" do
      conv = %Conversation{conversation_id: "c1", validated_codes: ["I10"]}

      cmd = %RejectCode{
        conversation_id: "c1",
        code_id: "x",
        cie10_code: "I10",
        rejection_reason: "cambio de opinión",
        rejected_by: "codificador"
      }

      assert {:error, :cannot_reject_validated_code} = Conversation.execute(conv, cmd)
    end
  end
end
