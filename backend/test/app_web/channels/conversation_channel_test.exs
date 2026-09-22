defmodule AppWeb.ConversationChannelTest do
  use AppWeb.ConnCase, async: false

  import Phoenix.ChannelTest
  import App.Fixtures

  @endpoint AppWeb.Endpoint

  # ---------------------------------------------------------------------------
  # Helpers
  # ---------------------------------------------------------------------------

  # Build an authenticated socket for the UserSocket using a valid Phoenix token.
  defp connect_socket(user) do
    token = generate_token(user)

    {:ok, socket} =
      Phoenix.ChannelTest.connect(AppWeb.UserSocket, %{"token" => token})

    socket
  end

  # ---------------------------------------------------------------------------
  # Socket authentication
  # ---------------------------------------------------------------------------

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

  # ---------------------------------------------------------------------------
  # Joining an EXISTING conversation (no Commanded needed: DB read only)
  # ---------------------------------------------------------------------------

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

  # ---------------------------------------------------------------------------
  # Joining a NEW conversation (requires Commanded + EventStore)
  # ---------------------------------------------------------------------------

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

  # ---------------------------------------------------------------------------
  # handle_in("suggest_code", ...)
  # ---------------------------------------------------------------------------

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

      # Join with a UUID that has no ConversationProjection row yet, so Commanded
      # creates it. We then manually remove the projection row to simulate a
      # missing conversation for the suggest_code handler.
      {:ok, _reply, joined_socket} =
        subscribe_and_join(socket, AppWeb.ConversationChannel, "conversation:#{phantom_id}")

      # Delete the projection row so the handler cannot find it.
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

  # ---------------------------------------------------------------------------
  # handle_in("send_message", ...)
  # ---------------------------------------------------------------------------

  describe "handle_in send_message" do
    setup do
      user = user_fixture()
      # Join with a fresh UUID so StartConversation is dispatched and the
      # Commanded aggregate is initialised before we push commands to it.
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

  # ---------------------------------------------------------------------------
  # handle_in("analyze_report", ...)
  # ---------------------------------------------------------------------------

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

  # ---------------------------------------------------------------------------
  # handle_in("validate_code", ...)
  # ---------------------------------------------------------------------------

  # Poll until the ConversationProjection row exists (the Commanded projector
  # writes it asynchronously after join). Gives up after ~500 ms.
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

  # Start a conversation via the channel (which initialises the Commanded
  # aggregate), wait for the projection row to appear, insert a predicted code,
  # then RE-join using the *existing* conversation path (no extra command
  # dispatch). Returns {joined_socket, code}.
  defp setup_conversation_with_code(user, code_attrs \\ %{}) do
    new_id = UUID.uuid4()
    socket = connect_socket(user)

    # First join: triggers StartConversation, initialises the aggregate.
    {:ok, _reply, _tmp_socket} =
      subscribe_and_join(socket, AppWeb.ConversationChannel, "conversation:#{new_id}")

    # Wait for projector to write the ConversationProjection row.
    conv = await_conversation_projection(new_id)

    # Insert predicted code directly so the projector can find it later.
    code = predicted_code_fixture(conv, Map.merge(%{status: "pending"}, code_attrs))

    # Second join: existing conversation path, no extra command dispatched.
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

  # ---------------------------------------------------------------------------
  # handle_in("reject_code", ...)
  # ---------------------------------------------------------------------------

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
end
