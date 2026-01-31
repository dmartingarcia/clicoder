defmodule AppWeb.ConversationChannel do
  @moduledoc """
  Channel para el chatbot en tiempo real
  """
  use AppWeb, :channel

  alias App.CommandedApplication
  alias App.Commands.{StartConversation, SendMessage, AnalyzeReport, ValidateCode, RejectCode}
  alias App.Repo
  alias App.Projections.{ConversationProjection, MessageProjection, PredictedCodeProjection}

  require Logger
  import Ecto.Query

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
    message_id = UUID.uuid4()

    cmd = %AnalyzeReport{
      conversation_id: conversation_id,
      message_id: message_id,
      report_text: report_text
    }

    case CommandedApplication.dispatch(cmd) do
      :ok ->
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
  def handle_in("reject_code", %{"code_id" => code_id, "cie10_code" => cie10_code, "reason" => reason}, socket) do
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
    conversation = Repo.get_by!(ConversationProjection, conversation_id: conversation_id)
    |> Repo.preload([:messages, :predicted_codes])

    %{
      messages: Enum.map(conversation.messages, &format_message/1),
      predicted_codes: Enum.map(conversation.predicted_codes, &format_code/1)
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
      status: code.status
    }
  end

  defp call_ai_engine(conversation_id, message_id, report_text, socket) do
    ai_url = Application.get_env(:app, :ai_engine_url, "http://localhost:8000")

    case Req.post("#{ai_url}/predict", json: %{text: report_text}) do
      {:ok, %{status: 200, body: body}} ->
        # Convertir formato de AI Engine al formato esperado por el comando
        codes = Enum.map(body["codes"], fn code ->
          %{
            "code" => code["code"],
            "reasoning" => code["reason"],
            "confidence" => 0.85  # Mock confidence por ahora
          }
        end)

        cmd = %App.Commands.ReceiveAIPrediction{
          conversation_id: conversation_id,
          message_id: message_id,
          predicted_codes: codes,
          reasoning: "Análisis automático basado en el texto ingresado",
          confidence_scores: Enum.map(codes, & &1["confidence"])
        }

        case CommandedApplication.dispatch(cmd) do
          :ok ->
            broadcast!(socket, "ai_prediction_received", %{
              message_id: message_id,
              codes: codes
            })

          {:error, reason} ->
            Logger.error("Failed to register AI prediction: #{inspect(reason)}")
        end

      {:error, reason} ->
        Logger.error("AI Engine request failed: #{inspect(reason)}")
        broadcast!(socket, "analysis_failed", %{
          message_id: message_id,
          error: "Failed to contact AI engine"
        })

      {:ok, %{status: status}} ->
        Logger.error("AI Engine returned status #{status}")
        broadcast!(socket, "analysis_failed", %{
          message_id: message_id,
          error: "AI engine error: HTTP #{status}"
        })
    end
  end
end
