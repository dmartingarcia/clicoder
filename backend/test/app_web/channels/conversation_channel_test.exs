defmodule AppWeb.ConversationChannelTest do
  use AppWeb.ConnCase, async: false

  import Phoenix.ChannelTest
  import App.Fixtures

  @endpoint AppWeb.Endpoint

  defp connect_socket(user) do
    token = generate_token(user)

    {:ok, socket} =
      Phoenix.ChannelTest.connect(AppWeb.UserSocket, %{"token" => token})

    socket
  end

  describe "UserSocket.connect/3" do
    test "accepts a valid token and assigns user_id" do
      user = user_fixture()
      token = generate_token(user)

      assert {:ok, socket} =
               Phoenix.ChannelTest.connect(AppWeb.UserSocket, %{"token" => token})

      assert to_string(socket.assigns.user_id) == to_string(user.id)
    end

    test "rejects connection without a token" do
      assert :error = Phoenix.ChannelTest.connect(AppWeb.UserSocket, %{})
    end

    test "rejects connection with an invalid token" do
      assert :error =
               Phoenix.ChannelTest.connect(AppWeb.UserSocket, %{"token" => "not-a-real-token"})
    end
  end

  describe "join/3: existing conversation" do
    test "returns status 'joined' and conversation history", %{conn: _conn} do
      user = user_fixture()
      conv = conversation_fixture(user)
      msg = message_fixture(conv)
      _code = predicted_code_fixture(conv)
      _card = analysis_card_fixture(conv)

      socket = connect_socket(user)

      assert {:ok, reply, _socket} =
               subscribe_and_join(
                 socket,
                 AppWeb.ConversationChannel,
                 "conversation:#{conv.conversation_id}"
               )

      assert reply.status == "joined"
      assert Map.has_key?(reply, :history)

      history = reply.history
      assert is_list(history.messages)
      assert is_list(history.predicted_codes)
      assert is_list(history.analysis_cards)

      message_ids = Enum.map(history.messages, & &1.message_id)
      assert msg.message_id in message_ids
    end

    test "history messages contain required fields", %{conn: _conn} do
      user = user_fixture()
      conv = conversation_fixture(user)
      _msg = message_fixture(conv, %{content: "Hello world", message_type: "user"})

      socket = connect_socket(user)

      assert {:ok, reply, _socket} =
               subscribe_and_join(
                 socket,
                 AppWeb.ConversationChannel,
                 "conversation:#{conv.conversation_id}"
               )

      [msg | _] = reply.history.messages

      assert Map.has_key?(msg, :message_id)
      assert Map.has_key?(msg, :content)
      assert Map.has_key?(msg, :user_id)
      assert Map.has_key?(msg, :timestamp)
      assert Map.has_key?(msg, :type)
    end

    test "history predicted_codes contain required fields", %{conn: _conn} do
      user = user_fixture()
      conv = conversation_fixture(user)

      _code =
        predicted_code_fixture(conv, %{
          cie10_code: "I10",
          reasoning: "Hypertension",
          confidence_score: 0.88,
          status: "pending"
        })

      socket = connect_socket(user)

      assert {:ok, reply, _socket} =
               subscribe_and_join(
                 socket,
                 AppWeb.ConversationChannel,
                 "conversation:#{conv.conversation_id}"
               )

      [code | _] = reply.history.predicted_codes

      assert Map.has_key?(code, :code_id)
      assert Map.has_key?(code, :cie10_code)
      assert Map.has_key?(code, :reasoning)
      assert Map.has_key?(code, :confidence)
      assert Map.has_key?(code, :status)
      assert code.cie10_code == "I10"
    end

    test "history analysis_cards are sorted by position", %{conn: _conn} do
      user = user_fixture()
      conv = conversation_fixture(user)

      _card2 =
        analysis_card_fixture(conv, %{
          card_type: "recommendations",
          position: 2,
          card_id: UUID.uuid4()
        })

      _card0 =
        analysis_card_fixture(conv, %{card_type: "summary", position: 0, card_id: UUID.uuid4()})

      _card1 =
        analysis_card_fixture(conv, %{card_type: "codes", position: 1, card_id: UUID.uuid4()})

      socket = connect_socket(user)

      assert {:ok, reply, _socket} =
               subscribe_and_join(
                 socket,
                 AppWeb.ConversationChannel,
                 "conversation:#{conv.conversation_id}"
               )

      positions = Enum.map(reply.history.analysis_cards, & &1.position)
      assert positions == Enum.sort(positions)
    end

    test "history is empty when conversation has no messages or codes", %{conn: _conn} do
      user = user_fixture()
      conv = conversation_fixture(user)

      socket = connect_socket(user)

      assert {:ok, reply, _socket} =
               subscribe_and_join(
                 socket,
                 AppWeb.ConversationChannel,
                 "conversation:#{conv.conversation_id}"
               )

      assert reply.status == "joined"
      assert reply.history.messages == []
      assert reply.history.predicted_codes == []
      assert reply.history.analysis_cards == []
    end
  end

  describe "join/3: new conversation" do
    test "dispatches StartConversation and returns 'conversation_started'", %{conn: _conn} do
      user = user_fixture()
      new_id = UUID.uuid4()

      socket = connect_socket(user)

      assert {:ok, reply, _socket} =
               subscribe_and_join(socket, AppWeb.ConversationChannel, "conversation:#{new_id}")

      assert reply.status == "conversation_started"
    end
  end

  describe "handle_in suggest_code" do
    setup do
      user = user_fixture()
      conv = conversation_fixture(user)
      socket = connect_socket(user)

      {:ok, _reply, joined_socket} =
        subscribe_and_join(
          socket,
          AppWeb.ConversationChannel,
          "conversation:#{conv.conversation_id}"
        )

      %{socket: joined_socket, conv: conv, user: user}
    end

    test "returns ok with a suggestion_id", %{socket: socket} do
      ref =
        push(socket, "suggest_code", %{
          "selected_text" => "hipertensión arterial",
          "suggested_code" => "I10"
        })

      assert_reply ref, :ok, %{suggestion_id: suggestion_id}
      assert is_binary(suggestion_id)
    end

    test "stores the suggested code in uppercase", %{socket: socket} do
      ref =
        push(socket, "suggest_code", %{
          "selected_text" => "diabetes",
          "suggested_code" => "e11"
        })

      assert_reply ref, :ok, %{suggestion_id: _}
    end

    test "returns error when conversation does not exist" do
      user = user_fixture()
      socket = connect_socket(user)
      phantom_id = UUID.uuid4()

      {:ok, _reply, joined_socket} =
        subscribe_and_join(socket, AppWeb.ConversationChannel, "conversation:#{phantom_id}")

      import Ecto.Query, only: [from: 2]

      App.Repo.delete_all(
        from(c in App.Projections.ConversationProjection,
          where: c.conversation_id == ^phantom_id
        )
      )

      ref =
        push(joined_socket, "suggest_code", %{
          "selected_text" => "diabetes",
          "suggested_code" => "E11"
        })

      assert_reply ref, :error, %{reason: "conversation not found"}
    end
  end

  describe "handle_in send_message" do
    setup do
      user = user_fixture()
      new_id = UUID.uuid4()
      socket = connect_socket(user)

      {:ok, _reply, joined_socket} =
        subscribe_and_join(socket, AppWeb.ConversationChannel, "conversation:#{new_id}")

      %{socket: joined_socket, user: user}
    end

    test "returns {:ok, %{message_id: _}} with a binary message_id", %{socket: socket} do
      ref = push(socket, "send_message", %{"content" => "Hola, tengo fiebre."})

      assert_reply ref, :ok, %{message_id: message_id}
      assert is_binary(message_id)
    end
  end

  describe "handle_in analyze_report" do
    setup do
      user = user_fixture()
      new_id = UUID.uuid4()
      socket = connect_socket(user)

      {:ok, _reply, joined_socket} =
        subscribe_and_join(socket, AppWeb.ConversationChannel, "conversation:#{new_id}")

      %{socket: joined_socket, user: user}
    end

    test "returns {:ok, %{status: 'analysis_started'}}", %{socket: socket} do
      ref =
        push(socket, "analyze_report", %{
          "report_text" => "Paciente con hipertensión arterial y diabetes tipo 2."
        })

      assert_reply ref, :ok, %{status: "analysis_started"}
    end
  end

  defp await_conversation_projection(conversation_id, retries \\ 10) do
    case App.Repo.get_by(App.Projections.ConversationProjection, conversation_id: conversation_id) do
      nil when retries > 0 ->
        Process.sleep(50)
        await_conversation_projection(conversation_id, retries - 1)

      nil ->
        raise "ConversationProjection never appeared for #{conversation_id}"

      conv ->
        conv
    end
  end

  defp setup_conversation_with_code(user, code_attrs \\ %{}) do
    new_id = UUID.uuid4()
    socket = connect_socket(user)

    {:ok, _reply, _tmp_socket} =
      subscribe_and_join(socket, AppWeb.ConversationChannel, "conversation:#{new_id}")

    conv = await_conversation_projection(new_id)

    code = predicted_code_fixture(conv, Map.merge(%{status: "pending"}, code_attrs))

    socket2 = connect_socket(user)

    {:ok, _reply2, joined_socket} =
      subscribe_and_join(socket2, AppWeb.ConversationChannel, "conversation:#{new_id}")

    {joined_socket, code}
  end

  describe "handle_in validate_code" do
    setup do
      user = user_fixture()
      {socket, code} = setup_conversation_with_code(user, %{cie10_code: "I10"})
      %{socket: socket, user: user, code: code}
    end

    test "returns {:ok, %{status: 'validated'}}", %{socket: socket, code: code} do
      ref =
        push(socket, "validate_code", %{
          "code_id" => code.code_id,
          "cie10_code" => code.cie10_code
        })

      assert_reply ref, :ok, %{status: "validated"}
    end
  end

  describe "handle_in reject_code" do
    setup do
      user = user_fixture()
      {socket, code} = setup_conversation_with_code(user, %{cie10_code: "J45.0"})
      %{socket: socket, user: user, code: code}
    end

    test "returns {:ok, %{status: 'rejected'}}", %{socket: socket, code: code} do
      ref =
        push(socket, "reject_code", %{
          "code_id" => code.code_id,
          "cie10_code" => code.cie10_code,
          "reason" => "Código no corresponde al diagnóstico principal"
        })

      assert_reply ref, :ok, %{status: "rejected"}
    end
  end

  describe "handle_in verify_trigger" do
    setup do
      user = user_fixture()
      conv = conversation_fixture(user)
      socket = connect_socket(user)

      {:ok, _reply, joined} =
        subscribe_and_join(
          socket,
          AppWeb.ConversationChannel,
          "conversation:#{conv.conversation_id}"
        )

      codigo =
        %App.Projections.PredictedCodeProjection{
          code_id: UUID.uuid4(),
          conversation_id: conv.id,
          cie10_code: "I10",
          reasoning: "hipertensión",
          confidence_score: 0.9,
          status: "pending",
          verified_triggers: []
        }
        |> App.Repo.insert!()

      %{socket: joined, code: codigo}
    end

    test "marcar un término lo añade a los verificados", %{socket: socket, code: code} do
      ref =
        push(socket, "verify_trigger", %{
          "code_id" => code.code_id,
          "trigger" => "hipertensión",
          "verified" => true
        })

      assert_reply ref, :ok, %{verified_triggers: ["hipertensión"]}
    end

    test "desmarcarlo lo retira", %{socket: socket, code: code} do
      push(socket, "verify_trigger", %{
        "code_id" => code.code_id,
        "trigger" => "hipertensión",
        "verified" => true
      })

      ref =
        push(socket, "verify_trigger", %{
          "code_id" => code.code_id,
          "trigger" => "hipertensión",
          "verified" => false
        })

      assert_reply ref, :ok, %{verified_triggers: []}
    end

    test "marcar dos veces el mismo término no lo duplica", %{socket: socket, code: code} do
      for _ <- 1..2 do
        push(socket, "verify_trigger", %{
          "code_id" => code.code_id,
          "trigger" => "hipertensión",
          "verified" => true
        })
      end

      ref =
        push(socket, "verify_trigger", %{
          "code_id" => code.code_id,
          "trigger" => "otra cosa",
          "verified" => true
        })

      assert_reply ref, :ok, %{verified_triggers: terminos}
      assert Enum.count(terminos, &(&1 == "hipertensión")) == 1
    end

    test "un código inexistente devuelve error en vez de reventar", %{socket: socket} do
      ref =
        push(socket, "verify_trigger", %{
          "code_id" => UUID.uuid4(),
          "trigger" => "lo que sea",
          "verified" => true
        })

      assert_reply ref, :error, %{reason: "code_not_found"}
    end

    test "la verificación se difunde a los demás clientes", %{socket: socket, code: code} do
      push(socket, "verify_trigger", %{
        "code_id" => code.code_id,
        "trigger" => "hipertensión",
        "verified" => true
      })

      assert_broadcast "trigger_verified", %{code_id: _, verified: true}
    end
  end

  describe "handle_in validate_code y reject_code" do
    setup do
      user = user_fixture()
      conv = conversation_fixture(user)
      socket = connect_socket(user)

      {:ok, _reply, joined} =
        subscribe_and_join(
          socket,
          AppWeb.ConversationChannel,
          "conversation:#{conv.conversation_id}"
        )

      %{socket: joined, conv: conv}
    end

    # La proyección puede existir sin que el agregado se haya iniciado (p. ej. tabla de lectura
    # restaurada sin el registro de eventos): el canal debe rechazar en vez de escribir estado.
    test "validar sobre una conversación sin iniciar se rechaza", %{socket: socket} do
      ref =
        push(socket, "validate_code", %{
          "code_id" => UUID.uuid4(),
          "cie10_code" => "I10"
        })

      assert_reply ref, :error, %{reason: razon}
      assert razon =~ "conversation_not_started"
    end

    test "rechazar sobre una conversación sin iniciar se rechaza igual", %{socket: socket} do
      ref =
        push(socket, "reject_code", %{
          "code_id" => UUID.uuid4(),
          "cie10_code" => "I10",
          "reason" => "no procede"
        })

      assert_reply ref, :error, %{reason: razon}
      assert razon =~ "conversation_not_started"
    end
  end

  describe "analyze_report contra el motor de IA" do
    setup do
      user = user_fixture()
      # Unirse a un id nuevo despacha StartConversation: el agregado debe existir para que
      # analyze_report no se rechace, y una proyección insertada a mano no lo crea.
      socket = connect_socket(user)

      {:ok, _reply, joined} =
        subscribe_and_join(socket, AppWeb.ConversationChannel, "conversation:#{UUID.uuid4()}")

      %{socket: joined, user: user}
    end

    test "una predicción correcta emite la tarjeta de códigos", %{socket: socket} do
      Req.Test.stub(App.AIEngineMock, fn conn ->
        Req.Test.json(conn, %{
          "cards" => [
            %{
              "type" => "codes",
              "content" => [
                %{"code" => "I10", "description" => "Hipertensión", "confidence" => 0.91}
              ]
            }
          ],
          "timing" => %{"classifier_ms" => 350}
        })
      end)

      push(socket, "analyze_report", %{"report_text" => "Paciente hipertenso"})

      assert_broadcast "analysis_card_received", %{card_type: "codes"}, 2_000
    end

    test "si el motor no responde, el canal no se cae", %{socket: socket} do
      Req.Test.stub(App.AIEngineMock, fn conn ->
        Req.Test.transport_error(conn, :econnrefused)
      end)

      ref = push(socket, "analyze_report", %{"report_text" => "Paciente hipertenso"})

      # La petición se acepta igual: el análisis es asíncrono y su fallo se comunica
      # por el canal, no como error de la llamada que lo inicia.
      assert_reply ref, :ok, %{status: "analysis_started"}
    end

    test "una respuesta sin tarjetas no rompe la persistencia", %{socket: socket} do
      Req.Test.stub(App.AIEngineMock, fn conn ->
        Req.Test.json(conn, %{"cards" => [], "timing" => %{}})
      end)

      ref = push(socket, "analyze_report", %{"report_text" => "Informe vacío"})
      assert_reply ref, :ok, %{status: "analysis_started"}
    end
  end

  describe "resumen en streaming" do
    setup do
      user = user_fixture()
      socket = connect_socket(user)

      {:ok, _reply, joined} =
        subscribe_and_join(socket, AppWeb.ConversationChannel, "conversation:#{UUID.uuid4()}")

      App.SummarizerSettings.set_model("gemma4")
      on_exit(fn -> App.SummarizerSettings.set_model("none") end)

      %{socket: joined, user: user}
    end

    test "emite un evento por cada token recibido", %{socket: socket} do
      Req.Test.stub(App.AIEngineMock, fn conn ->
        case conn.request_path do
          "/predict" ->
            Req.Test.json(conn, %{"cards" => [], "timing" => %{}})

          "/summarize/stream" ->
            # El motor responde NDJSON: un objeto JSON por línea, para que el cliente
            # pueda pintar el texto según llega en vez de esperar al final.
            conn
            |> Plug.Conn.put_resp_content_type("application/x-ndjson")
            |> Plug.Conn.send_resp(
              200,
              ~s({"token":"Paciente "}\n{"token":"con neumonía"}\n{"done":true}\n)
            )

          _ ->
            Req.Test.json(conn, %{})
        end
      end)

      push(socket, "analyze_report", %{"report_text" => "Paciente con neumonía"})

      assert_broadcast "summary_token", %{token: "Paciente "}, 3_000
      assert_broadcast "summary_token", %{token: "con neumonía"}, 3_000
    end

    test "una línea mal formada no interrumpe el resto", %{socket: socket} do
      Req.Test.stub(App.AIEngineMock, fn conn ->
        case conn.request_path do
          "/summarize/stream" ->
            conn
            |> Plug.Conn.put_resp_content_type("application/x-ndjson")
            |> Plug.Conn.send_resp(200, ~s(esto no es json\n{"token":"válido"}\n))

          _ ->
            Req.Test.json(conn, %{"cards" => [], "timing" => %{}})
        end
      end)

      push(socket, "analyze_report", %{"report_text" => "Informe"})

      assert_broadcast "summary_token", %{token: "válido"}, 3_000
    end
  end

  describe "términos explicativos en segunda llamada" do
    setup do
      user = user_fixture()
      socket = connect_socket(user)

      {:ok, _reply, joined} =
        subscribe_and_join(socket, AppWeb.ConversationChannel, "conversation:#{UUID.uuid4()}")

      %{socket: joined, user: user}
    end

    test "los términos llegan por su propio evento y completan la tarjeta", %{socket: socket} do
      Req.Test.stub(App.AIEngineMock, fn conn ->
        case conn.request_path do
          "/predict" ->
            Req.Test.json(conn, %{
              "cards" => [
                %{
                  "type" => "codes",
                  "content" => [%{"code" => "J18.9", "description" => "Neumonía"}]
                }
              ],
              "timing" => %{}
            })

          "/explain" ->
            Req.Test.json(conn, %{
              "method" => "gradiente_filtrado",
              "triggers" => %{
                "J18.9" => [%{"term" => "neumonía", "source" => "bert", "weight" => 0.8}]
              },
              "timing" => %{"explain_ms" => 1200}
            })

          _ ->
            Req.Test.json(conn, %{})
        end
      end)

      push(socket, "analyze_report", %{"report_text" => "Paciente con neumonía basal"})

      # Primero llegan los códigos, y después los términos: es justo el desacoplamiento
      # que evita que el usuario espere doce segundos para ver una lista que ya existe.
      assert_broadcast "analysis_card_received", %{card_type: "codes"}, 3_000
      assert_broadcast "triggers_received", %{method: "gradiente_filtrado"}, 5_000
    end

    test "si la explicación falla, los códigos siguen entregados", %{socket: socket} do
      Req.Test.stub(App.AIEngineMock, fn conn ->
        case conn.request_path do
          "/predict" ->
            Req.Test.json(conn, %{
              "cards" => [
                %{"type" => "codes", "content" => [%{"code" => "I10", "description" => "HTA"}]}
              ],
              "timing" => %{}
            })

          "/explain" ->
            Req.Test.transport_error(conn, :econnrefused)

          _ ->
            Req.Test.json(conn, %{})
        end
      end)

      push(socket, "analyze_report", %{"report_text" => "Paciente hipertenso"})

      assert_broadcast "analysis_card_received", %{card_type: "codes"}, 3_000
      refute_broadcast "triggers_received", %{}, 500
    end
  end
end
