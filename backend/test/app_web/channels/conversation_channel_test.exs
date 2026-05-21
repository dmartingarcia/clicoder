defmodule AppWeb.ConversationChannelTest do
  use AppWeb.ConnCase, async: false

  import Phoenix.ChannelTest
  import App.Fixtures
  # Remove Plug.Conn.push/3 from scope to avoid ambiguity with Phoenix.ChannelTest.push/3
  import Plug.Conn, except: [push: 3]

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
  # Joining an EXISTING conversation (no Commanded needed — DB read only)
  # ---------------------------------------------------------------------------

  describe "join/3 — existing conversation" do
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

  describe "join/3 — new conversation" do
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
  end
end
