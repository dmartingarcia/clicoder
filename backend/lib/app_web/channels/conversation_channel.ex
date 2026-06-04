defmodule AppWeb.ConversationChannel do
  @moduledoc """
  Channel para el chatbot en tiempo real
  """
  use AppWeb, :channel

  alias App.CommandedApplication

  alias App.Commands.{
    StartConversation,
    SendMessage,
    AnalyzeReport,
    ReceiveAIPrediction,
    ValidateCode,
    RejectCode
  }

  alias App.Repo

  alias App.Projections.{
    ConversationProjection,
    PredictedCodeProjection,
    AnalysisCardProjection,
    CodeSuggestionProjection
  }

  require Logger

  @impl true
  def join("conversation:" <> conversation_id, _payload, socket) do
    case Repo.get_by(ConversationProjection, conversation_id: conversation_id) do
      nil ->
        user_id = socket.assigns.user_id

        cmd = %StartConversation{
          conversation_id: conversation_id,
          user_id: user_id,
          started_at: DateTime.utc_now()
        }

        case CommandedApplication.dispatch(cmd) do
          :ok ->
            socket = assign(socket, :conversation_id, conversation_id)
            {:ok, %{status: "conversation_started"}, socket}

          {:error, reason} ->
            {:error, %{reason: inspect(reason)}}
        end

      _conversation ->
        socket = assign(socket, :conversation_id, conversation_id)
        history = load_conversation_history(conversation_id)
        {:ok, %{status: "joined", history: history}, socket}
    end
  end

  @impl true
  def handle_in("send_message", %{"content" => content}, socket) do
    conversation_id = socket.assigns.conversation_id
    user_id = socket.assigns.user_id
    message_id = UUID.uuid4()

    cmd = %SendMessage{
      conversation_id: conversation_id,
      message_id: message_id,
      user_id: user_id,
      content: content,
      timestamp: DateTime.utc_now()
    }

    case CommandedApplication.dispatch(cmd) do
      :ok ->
        broadcast!(socket, "new_message", %{
          message_id: message_id,
          content: content,
          user_id: user_id,
          timestamp: DateTime.utc_now()
        })

        # Llamar al AI Engine para analizar el texto
        Task.start(fn ->
          call_ai_engine(conversation_id, message_id, content, socket)
        end)

        {:reply, {:ok, %{message_id: message_id}}, socket}

      {:error, reason} ->
        {:reply, {:error, %{reason: inspect(reason)}}, socket}
    end
  end

  @impl true
  def handle_in("analyze_report", %{"report_text" => report_text}, socket) do
    conversation_id = socket.assigns.conversation_id
    user_id = socket.assigns.user_id
    message_id = UUID.uuid4()
    timestamp = DateTime.utc_now()

    # Save the report as a message so it persists across reloads
    msg_cmd = %SendMessage{
      conversation_id: conversation_id,
      message_id: message_id,
      user_id: user_id,
      content: report_text,
      timestamp: timestamp
    }

    CommandedApplication.dispatch(msg_cmd)

    analyze_cmd = %AnalyzeReport{
      conversation_id: conversation_id,
      message_id: message_id,
      report_text: report_text
    }

    case CommandedApplication.dispatch(analyze_cmd) do
      :ok ->
        broadcast!(socket, "new_message", %{
          message_id: message_id,
          content: report_text,
          user_id: user_id,
          timestamp: timestamp
        })

        broadcast!(socket, "analysis_started", %{message_id: message_id})

        Task.start(fn ->
          call_ai_engine(conversation_id, message_id, report_text, socket)
        end)

        {:reply, {:ok, %{status: "analysis_started"}}, socket}

      {:error, reason} ->
        {:reply, {:error, %{reason: inspect(reason)}}, socket}
    end
  end

  @impl true
  def handle_in("validate_code", %{"code_id" => code_id, "cie10_code" => cie10_code}, socket) do
    conversation_id = socket.assigns.conversation_id
    user_id = socket.assigns.user_id

    cmd = %ValidateCode{
      conversation_id: conversation_id,
      code_id: code_id,
      cie10_code: cie10_code,
      validated_by: user_id,
      validation_timestamp: DateTime.utc_now()
    }

    case CommandedApplication.dispatch(cmd) do
      :ok ->
        broadcast!(socket, "code_validated", %{code_id: code_id, cie10_code: cie10_code})
        {:reply, {:ok, %{status: "validated"}}, socket}

      {:error, reason} ->
        {:reply, {:error, %{reason: inspect(reason)}}, socket}
    end
  end

  @impl true
  def handle_in(
        "verify_trigger",
        %{"code_id" => code_id, "trigger" => trigger, "verified" => verified},
        socket
      ) do
    import Ecto.Query

    code = App.Repo.get_by(App.Projections.PredictedCodeProjection, code_id: code_id)

    if is_nil(code) do
      {:reply, {:error, %{reason: "code_not_found"}}, socket}
    else
      new_triggers =
        if verified do
          Enum.uniq([trigger | code.verified_triggers || []])
        else
          Enum.reject(code.verified_triggers || [], &(&1 == trigger))
        end

      code
      |> Ecto.Changeset.change(verified_triggers: new_triggers)
      |> App.Repo.update!()

      broadcast!(socket, "trigger_verified", %{
        code_id: code_id,
        trigger: trigger,
        verified: verified,
        verified_triggers: new_triggers
      })

      {:reply, {:ok, %{verified_triggers: new_triggers}}, socket}
    end
  end

  @impl true
  def handle_in(
        "suggest_code",
        %{"selected_text" => selected_text, "suggested_code" => suggested_code},
        socket
      ) do
    conversation_id = socket.assigns.conversation_id
    user_id = socket.assigns.user_id

    case Repo.get_by(ConversationProjection, conversation_id: conversation_id) do
      nil ->
        {:reply, {:error, %{reason: "conversation not found"}}, socket}

      conversation ->
        changeset =
          CodeSuggestionProjection.changeset(
            %CodeSuggestionProjection{},
            %{
              suggestion_id: UUID.uuid4(),
              conversation_id: conversation.id,
              selected_text: selected_text,
              suggested_code: String.upcase(suggested_code),
              suggested_by: user_id
            }
          )

        case Repo.insert(changeset) do
          {:ok, suggestion} ->
            {:reply, {:ok, %{suggestion_id: suggestion.suggestion_id}}, socket}

          {:error, reason} ->
            {:reply, {:error, %{reason: inspect(reason)}}, socket}
        end
    end
  end

  @impl true
  def handle_in(
        "reject_code",
        %{"code_id" => code_id, "cie10_code" => cie10_code, "reason" => reason},
        socket
      ) do
    conversation_id = socket.assigns.conversation_id
    user_id = socket.assigns.user_id

    cmd = %RejectCode{
      conversation_id: conversation_id,
      code_id: code_id,
      cie10_code: cie10_code,
      rejection_reason: reason,
      rejected_by: user_id
    }

    case CommandedApplication.dispatch(cmd) do
      :ok ->
        broadcast!(socket, "code_rejected", %{code_id: code_id, cie10_code: cie10_code})
        {:reply, {:ok, %{status: "rejected"}}, socket}

      {:error, error} ->
        {:reply, {:error, %{reason: inspect(error)}}, socket}
    end
  end

  defp load_conversation_history(conversation_id) do
    conversation =
      Repo.get_by!(ConversationProjection, conversation_id: conversation_id)
      |> Repo.preload([:messages, :predicted_codes, :analysis_cards])

    cards =
      conversation.analysis_cards
      |> Enum.sort_by(& &1.position)
      |> Enum.map(&format_card/1)

    %{
      messages: Enum.map(conversation.messages, &format_message/1),
      predicted_codes: Enum.map(conversation.predicted_codes, &format_code/1),
      analysis_cards: cards
    }
  end

  defp format_message(msg) do
    %{
      message_id: msg.message_id,
      content: msg.content,
      user_id: msg.user_id,
      timestamp: msg.timestamp,
      type: msg.message_type
    }
  end

  defp format_code(code) do
    %{
      code_id: code.code_id,
      cie10_code: code.cie10_code,
      reasoning: code.reasoning,
      confidence: code.confidence_score,
      status: code.status,
      verified_triggers: code.verified_triggers || []
    }
  end

  defp format_card(card) do
    content =
      case card.card_type do
        "codes" ->
          case Jason.decode(card.content) do
            {:ok, decoded} -> decoded
            _ -> card.content
          end

        _ ->
          card.content
      end

    %{
      card_id: card.card_id,
      card_type: card.card_type,
      content: content,
      position: card.position,
      message_id: card.message_id
    }
  end

  # Inserts analysis cards directly (fallback when CQRS projection is delayed/fails).
  defp persist_cards_direct(conversation_id, message_id, cards) do
    conversation = Repo.get_by(ConversationProjection, conversation_id: conversation_id)

    unless is_nil(conversation) do
      cards
      |> Enum.with_index()
      |> Enum.each(fn {card, idx} ->
        card_type = card["type"]
        card_content = card["content"]
        content = if card_type == "codes", do: Jason.encode!(card_content), else: card_content

        %AnalysisCardProjection{
          card_id: UUID.uuid4(),
          card_type: card_type,
          content: content,
          position: idx,
          message_id: message_id,
          conversation_id: conversation.id
        }
        |> Repo.insert(on_conflict: :nothing)
      end)
    end
  end

  # Always inserts predicted codes directly with pre-generated UUIDs so we can
  # broadcast them immediately in analysis_complete (avoids async CQRS timing issues).
  defp persist_predicted_codes_direct(conversation_id, cards) do
    conversation = Repo.get_by(ConversationProjection, conversation_id: conversation_id)

    if is_nil(conversation) do
      []
    else
      codes_content =
        cards
        |> Enum.find(%{}, fn c -> c["type"] == "codes" end)
        |> Map.get("content", [])

      Enum.map(codes_content, fn code ->
        code_id = UUID.uuid4()

        %PredictedCodeProjection{
          code_id: code_id,
          cie10_code: code["code"],
          reasoning: code["reason"] || code["reasoning"],
          confidence_score: code["confidence"],
          status: "pending",
          conversation_id: conversation.id
        }
        |> Repo.insert(on_conflict: :nothing)

        %{
          code_id: code_id,
          cie10_code: code["code"],
          reasoning: code["reason"] || code["reasoning"],
          confidence: code["confidence"],
          status: "pending"
        }
      end)
    end
  end

  defp call_ai_engine(conversation_id, message_id, report_text, socket) do
    ai_url = Application.get_env(:app, :ai_engine_url, "http://localhost:8000")
    engine = App.AIEngineSettings.get_engine()

    Logger.info("Iniciando llamada a AI Engine",
      ai_url: ai_url,
      engine: engine,
      conversation_id: conversation_id,
      message_id: message_id
    )

    case Req.post("#{ai_url}/predict",
           json: %{text: report_text, engine: engine},
           receive_timeout: 60_000
         ) do
      {:ok, %{status: 200, body: body}} ->
        cards = body["cards"] || []
        timing = body["timing"] || %{}

        Logger.info("AI Engine response timings",
          classifier_ms: timing["classifier_ms"],
          summarizer_ms: timing["summarizer_ms"],
          total_ms: timing["total_ms"],
          engine: engine,
          conversation_id: conversation_id
        )

        cmd = %ReceiveAIPrediction{
          conversation_id: conversation_id,
          message_id: message_id,
          cards: cards,
          predicted_codes: [],
          reasoning: "Análisis automático",
          confidence_scores: [],
          engine: engine
        }

        case CommandedApplication.dispatch(cmd) do
          :ok ->
            :ok

          {:error, reason} ->
            Logger.warning(
              "ReceiveAIPrediction dispatch failed (#{inspect(reason)}), persisting cards directly"
            )

            persist_cards_direct(conversation_id, message_id, cards)
        end

        Enum.each(cards, fn card ->
          broadcast!(socket, "analysis_card_received", %{
            message_id: message_id,
            card_id: UUID.uuid4(),
            card_type: card["type"],
            content: card["content"]
          })
        end)

        # Insert predicted codes synchronously with known UUIDs so analysis_complete
        # always carries the correct code_id values (avoids async CQRS timing race).
        predicted_codes = persist_predicted_codes_direct(conversation_id, cards)

        broadcast!(socket, "analysis_complete", %{
          message_id: message_id,
          predicted_codes: predicted_codes,
          engine: engine
        })

      {:error, reason} ->
        Logger.error("AI Engine request failed",
          reason: inspect(reason),
          ai_url: ai_url,
          conversation_id: conversation_id,
          message_id: message_id
        )

        broadcast!(socket, "analysis_failed", %{
          message_id: message_id,
          error: "No se pudo contactar con el motor de análisis"
        })

      {:ok, %{status: status, body: body}} ->
        Logger.error("AI Engine returned HTTP #{status}",
          status: status,
          body: inspect(body),
          ai_url: ai_url,
          conversation_id: conversation_id,
          message_id: message_id
        )

        broadcast!(socket, "analysis_failed", %{
          message_id: message_id,
          error: "Error del motor de análisis: HTTP #{status}"
        })
    end
  end
end
