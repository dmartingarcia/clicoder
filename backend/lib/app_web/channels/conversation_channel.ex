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
    MessageProjection,
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
    persist_report_text(conversation_id, message_id, user_id, report_text, timestamp)

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

  # El texto del informe no viaja en los eventos (categoria especial del articulo 9 del RGPD, y
  # el registro de eventos no se puede borrar). Se escribe aqui, sobre la proyeccion, que es lo
  # que elimina el purgado. El upsert cubre las dos carreras posibles con el proyector: si llega
  # antes, actualiza la fila que este creo; si llega despues, no pisa nada.
  defp persist_report_text(conversation_id, message_id, user_id, texto, timestamp) do
    case Repo.get_by(ConversationProjection, conversation_id: conversation_id) do
      nil ->
        :ok

      conversation ->
        %MessageProjection{
          message_id: message_id,
          content: texto,
          user_id: user_id,
          timestamp: DateTime.truncate(timestamp, :second),
          message_type: "user_message",
          conversation_id: conversation.id
        }
        |> Repo.insert(
          on_conflict: [set: [content: texto]],
          conflict_target: :message_id
        )

        :ok
    end
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

  # La atribución de términos cuesta dos órdenes de magnitud más que predecir (medido: 0,35 s
  # la predicción frente a 13 s la explicación con la estrategia adoptada), así que no puede
  # bloquear la respuesta. Se pide en una segunda llamada y se emite cuando llega: el cliente
  # pinta los códigos de inmediato y completa los términos después, mostrando un indicador
  # mientras tanto. Con el motor fusionado, los términos del diccionario ya viajan con la
  # predicción porque su coincidencia se calculó para ordenar los códigos.
  defp request_triggers_async(ai_url, report_text, message_id, conversation_id, cards, socket) do
    codes =
      cards
      |> Enum.find(%{}, fn c -> c["type"] == "codes" end)
      |> Map.get("content", [])
      |> Enum.map(& &1["code"])
      |> Enum.reject(&is_nil/1)

    if codes != [] do
      Task.start(fn ->
        peticion = [
          json: %{
            text: report_text,
            codes: codes,
            method: App.AIEngineSettings.get_explain_method()
          },
          receive_timeout: 180_000
        ]

        case Req.post("#{ai_url}/explain", peticion ++ req_opts()) do
          {:ok, %{status: 200, body: body}} ->
            triggers = body["triggers"] || %{}
            persist_triggers(conversation_id, message_id, triggers)

            Logger.info("Términos explicativos recibidos",
              method: body["method"],
              explain_ms: get_in(body, ["timing", "explain_ms"]),
              conversation_id: conversation_id
            )

            broadcast!(socket, "triggers_received", %{
              message_id: message_id,
              method: body["method"],
              triggers: triggers
            })

          otro ->
            # Que falle la explicación no invalida la predicción: el usuario conserva sus
            # códigos y la tarjeta se queda sin términos en lugar de romperse.
            Logger.warning("No se pudieron obtener los términos explicativos: #{inspect(otro)}")
        end
      end)
    end
  end

  # Completa la tarjeta ya guardada con los términos que llegaron después, para que al
  # recargar la conversación sigan estando.
  defp persist_triggers(conversation_id, message_id, triggers) do
    conversation = Repo.get_by(ConversationProjection, conversation_id: conversation_id)

    with false <- is_nil(conversation),
         card when not is_nil(card) <-
           Repo.get_by(AnalysisCardProjection,
             message_id: message_id,
             conversation_id: conversation.id,
             card_type: "codes"
           ),
         {:ok, contenido} <- Jason.decode(card.content) do
      completado =
        Enum.map(contenido, fn code ->
          terminos = Map.get(triggers, code["code"], [])

          code
          |> Map.put("triggers", Enum.map(terminos, & &1["term"]))
          |> Map.put("trigger_detail", terminos)
          |> Map.put("triggers_complete", true)
        end)

      card
      |> Ecto.Changeset.change(content: Jason.encode!(completado))
      |> Repo.update()
    else
      _ -> :ok
    end
  end

  # Always inserts predicted codes directly with pre-generated UUIDs so we can
  # broadcast them immediately in analysis_complete (avoids async CQRS timing issues).
  # Auditoria: deja en el registro inmutable que informe se analizo, con que motor y con que
  # pesos. Sin la version del modelo no se puede reconstruir a posteriori por que el sistema
  # propuso un codigo concreto, que es justo lo que exige la trazabilidad clinica.
  defp registrar_prediccion(conversation_id, message_id, cards, engine, model_version) do
    codigos =
      cards
      |> Enum.find(%{}, fn c -> c["type"] == "codes" end)
      |> Map.get("content", [])

    cmd = %ReceiveAIPrediction{
      conversation_id: conversation_id,
      message_id: message_id,
      cards: [],
      predicted_codes: Enum.map(codigos, & &1["code"]),
      confidence_scores: Enum.map(codigos, & &1["confidence"]),
      engine: engine,
      model_version: model_version
    }

    case CommandedApplication.dispatch(cmd) do
      :ok ->
        :ok

      {:error, reason} ->
        Logger.error("No se pudo registrar la prediccion",
          reason: inspect(reason),
          conversation_id: conversation_id
        )
    end
  end

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
    language = get_user_language(socket.assigns.user_id)

    summarizer_model = App.SummarizerSettings.get().model
    with_summary = summarizer_model != "none"

    Logger.info(
      "Iniciando análisis (predict + summarize/stream, summarizer=#{summarizer_model})",
      ai_url: ai_url,
      engine: engine,
      conversation_id: conversation_id,
      message_id: message_id
    )

    predict_task =
      Task.async(fn ->
        predict_with_retry(ai_url, %{text: report_text, engine: engine}, 2)
      end)

    summary_task =
      if with_summary do
        Task.async(fn -> do_stream_summary(ai_url, report_text, language, message_id, socket) end)
      end

    # ── Fase 1: códigos (rápidos, llegan antes del resumen) ──────────────────
    predicted_codes =
      case Task.await(predict_task, 60_000) do
        {:ok, %{status: 200, body: body}} ->
          cards = body["cards"] || []
          timing = body["timing"] || %{}

          Logger.info("Códigos recibidos",
            classifier_ms: timing["classifier_ms"],
            engine: engine,
            conversation_id: conversation_id
          )

          persist_cards_direct(conversation_id, message_id, cards)
          registrar_prediccion(conversation_id, message_id, cards, engine, body["model_version"])
          request_triggers_async(ai_url, report_text, message_id, conversation_id, cards, socket)

          Enum.each(cards, fn card ->
            broadcast!(socket, "analysis_card_received", %{
              message_id: message_id,
              card_id: UUID.uuid4(),
              card_type: card["type"],
              content: card["content"]
            })
          end)

          persist_predicted_codes_direct(conversation_id, cards)

        {:error, reason} ->
          Logger.error("AI Engine predict failed",
            reason: inspect(reason),
            ai_url: ai_url,
            conversation_id: conversation_id,
            message_id: message_id
          )

          broadcast!(socket, "analysis_failed", %{
            message_id: message_id,
            error: "No se pudo contactar con el motor de análisis"
          })

          []

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

          []
      end

    # ── Fase 2: resumen (los tokens ya llegaron en streaming) ────────────────
    if with_summary do
      full_summary = Task.await(summary_task, 120_000)

      unless full_summary == "" do
        summary_card = %{"type" => "summary", "content" => full_summary}
        persist_cards_direct(conversation_id, message_id, [summary_card])

        broadcast!(socket, "analysis_card_received", %{
          message_id: message_id,
          card_id: UUID.uuid4(),
          card_type: "summary",
          content: full_summary
        })
      end
    end

    broadcast!(socket, "analysis_complete", %{
      message_id: message_id,
      predicted_codes: predicted_codes,
      engine: engine
    })
  end

  defp do_stream_summary(ai_url, text, language, message_id, socket) do
    Process.put(:summary_buf, "")
    Process.put(:summary_acc, [])

    settings = App.SummarizerSettings.get()

    {system_tmpl, user_tmpl} =
      case settings.mode do
        "paraphrase" -> {settings.prompt_paraphrase, settings.user_prompt_paraphrase}
        _ -> {settings.prompt_summary, settings.user_prompt_summary}
      end

    fill = fn tmpl ->
      tmpl |> String.replace("{language}", language) |> String.replace("{text}", text)
    end

    peticion = [
      json: %{text: text, system_prompt: fill.(system_tmpl), user_prompt: fill.(user_tmpl)},
      receive_timeout: 120_000,
      decode_body: false,
      into: fn {:data, chunk}, {req, resp} ->
        buf = Process.get(:summary_buf, "")
        combined = buf <> chunk
        lines = String.split(combined, "\n")
        n = length(lines)
        complete = Enum.take(lines, n - 1)
        partial = List.last(lines) || ""
        Process.put(:summary_buf, partial)

        for line <- complete, String.trim(line) != "" do
          case Jason.decode(line) do
            {:ok, %{"token" => token}} when is_binary(token) and token != "" ->
              broadcast!(socket, "summary_token", %{message_id: message_id, token: token})
              Process.put(:summary_acc, [token | Process.get(:summary_acc, [])])

            _ ->
              :ok
          end
        end

        {:cont, {req, resp}}
      end
    ]

    Req.post("#{ai_url}/summarize/stream", peticion ++ req_opts())

    tokens = Enum.reverse(Process.get(:summary_acc, []))
    Process.delete(:summary_buf)
    Process.delete(:summary_acc)
    Enum.join(tokens)
  end

  @locale_to_language %{
    "es" => "español",
    "en" => "English",
    "fr" => "français",
    "de" => "Deutsch",
    "pt" => "português",
    "ca" => "català"
  }

  defp get_user_language(user_id) do
    locale =
      case App.Accounts.get_user(user_id) do
        nil -> "es"
        user -> user.locale || "es"
      end

    Map.get(@locale_to_language, locale, "español")
  end

  # Opciones de transporte inyectables: vacías en producción, con el plug de Req.Test en
  # pruebas. Sin esto la integración con el motor de IA no se puede ejercitar sin una red.
  defp req_opts, do: Application.get_env(:app, :ai_req_opts, [])

  defp predict_with_retry(ai_url, body, retries) do
    case Req.post("#{ai_url}/predict", [json: body, receive_timeout: 60_000] ++ req_opts()) do
      {:error, %{reason: reason}} when retries > 0 ->
        Logger.warning("Predict falló (#{inspect(reason)}), reintentando (#{retries} restantes)")
        predict_with_retry(ai_url, body, retries - 1)

      result ->
        result
    end
  end
end
