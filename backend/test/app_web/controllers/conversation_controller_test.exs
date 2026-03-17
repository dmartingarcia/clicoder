defmodule AppWeb.ConversationControllerTest do
  use AppWeb.ConnCase, async: true

  import App.Fixtures

  # ---------------------------------------------------------------------------
  # Helpers
  # ---------------------------------------------------------------------------

  defp authed_conn(conn, user) do
    {header_name, header_value} = auth_header(user)
    put_req_header(conn, header_name, header_value)
  end

  # ---------------------------------------------------------------------------
  # GET /api/conversations?user_id=<id>
  # ---------------------------------------------------------------------------

  describe "index/2 — active conversations" do
    test "returns only active (non-deleted) conversations for the user", %{conn: conn} do
      user = user_fixture()
      active1 = conversation_fixture(user)
      active2 = conversation_fixture(user)
      _trashed = deleted_conversation_fixture(user)

      conn =
        conn
        |> authed_conn(user)
        |> get("/api/conversations", %{"user_id" => user.id})

      assert %{"conversations" => list} = json_response(conn, 200)
      ids = Enum.map(list, & &1["conversation_id"])

      assert active1.conversation_id in ids
      assert active2.conversation_id in ids
      # Trashed conversation must not appear
      refute Enum.any?(list, fn c -> c["deleted_at"] != nil end)
    end

    test "does not return conversations belonging to a different user", %{conn: conn} do
      user = user_fixture()
      other_user = user_fixture()
      _other_conv = conversation_fixture(other_user)

      conn =
        conn
        |> authed_conn(user)
        |> get("/api/conversations", %{"user_id" => user.id})

      assert %{"conversations" => list} = json_response(conn, 200)
      assert list == []
    end

    test "returns 400 when user_id query param is missing", %{conn: conn} do
      user = user_fixture()

      conn =
        conn
        |> authed_conn(user)
        |> get("/api/conversations")

      assert %{"error" => _} = json_response(conn, 400)
    end

    test "returns 401 without authentication", %{conn: conn} do
      conn = get(conn, "/api/conversations", %{"user_id" => "some-id"})
      # RequireAuth halts with 401
      assert conn.status == 401
    end

    test "includes message_count and last_message fields", %{conn: conn} do
      user = user_fixture()
      conv = conversation_fixture(user)
      _msg = message_fixture(conv)

      conn =
        conn
        |> authed_conn(user)
        |> get("/api/conversations", %{"user_id" => user.id})

      assert %{"conversations" => [item | _]} = json_response(conn, 200)
      assert Map.has_key?(item, "message_count")
      assert Map.has_key?(item, "last_message")
    end

    test "returns an empty list when user has no conversations", %{conn: conn} do
      user = user_fixture()

      conn =
        conn
        |> authed_conn(user)
        |> get("/api/conversations", %{"user_id" => user.id})

      assert %{"conversations" => []} = json_response(conn, 200)
    end
  end

  # ---------------------------------------------------------------------------
  # GET /api/conversations/trash?user_id=<id>
  # ---------------------------------------------------------------------------

  describe "trash/2 — deleted conversations" do
    test "returns only soft-deleted conversations", %{conn: conn} do
      user = user_fixture()
      _active = conversation_fixture(user)
      trashed = deleted_conversation_fixture(user)

      conn =
        conn
        |> authed_conn(user)
        |> get("/api/conversations/trash", %{"user_id" => user.id})

      assert %{"conversations" => list} = json_response(conn, 200)
      ids = Enum.map(list, & &1["conversation_id"])

      assert trashed.conversation_id in ids
      # Active conversations must not appear
      assert Enum.all?(list, fn c -> c["deleted_at"] != nil end)
    end

    test "returns an empty list when trash is empty", %{conn: conn} do
      user = user_fixture()
      _active = conversation_fixture(user)

      conn =
        conn
        |> authed_conn(user)
        |> get("/api/conversations/trash", %{"user_id" => user.id})

      assert %{"conversations" => []} = json_response(conn, 200)
    end

    test "returns 400 when user_id is missing", %{conn: conn} do
      user = user_fixture()

      conn =
        conn
        |> authed_conn(user)
        |> get("/api/conversations/trash")

      assert %{"error" => _} = json_response(conn, 400)
    end

    test "returns 401 without authentication", %{conn: conn} do
      conn = get(conn, "/api/conversations/trash", %{"user_id" => "some-id"})
      assert conn.status == 401
    end
  end

  # ---------------------------------------------------------------------------
  # DELETE /api/conversations/:conversation_id
  # ---------------------------------------------------------------------------

  describe "delete/2 — soft delete" do
    test "soft-deletes an active conversation owned by the user", %{conn: conn} do
      user = user_fixture()
      conv = conversation_fixture(user)

      conn =
        conn
        |> authed_conn(user)
        |> delete("/api/conversations/#{conv.conversation_id}")

      assert %{"ok" => true} = json_response(conn, 200)

      # Verify deleted_at is now set in the database
      updated = App.Repo.get_by!(App.Projections.ConversationProjection,
        conversation_id: conv.conversation_id)
      assert updated.deleted_at != nil
    end

    test "returns 404 when conversation does not exist", %{conn: conn} do
      user = user_fixture()

      conn =
        conn
        |> authed_conn(user)
        |> delete("/api/conversations/nonexistent-id")

      assert %{"error" => _} = json_response(conn, 404)
    end

    test "returns 404 when conversation belongs to a different user", %{conn: conn} do
      user = user_fixture()
      other_user = user_fixture()
      other_conv = conversation_fixture(other_user)

      conn =
        conn
        |> authed_conn(user)
        |> delete("/api/conversations/#{other_conv.conversation_id}")

      assert %{"error" => _} = json_response(conn, 404)
    end

    test "returns 401 without authentication", %{conn: conn} do
      user = user_fixture()
      conv = conversation_fixture(user)

      conn = delete(conn, "/api/conversations/#{conv.conversation_id}")
      assert conn.status == 401
    end
  end

  # ---------------------------------------------------------------------------
  # PUT /api/conversations/:conversation_id/restore
  # ---------------------------------------------------------------------------

  describe "restore/2 — restore from trash" do
    test "restores a soft-deleted conversation", %{conn: conn} do
      user = user_fixture()
      conv = deleted_conversation_fixture(user)

      conn =
        conn
        |> authed_conn(user)
        |> put("/api/conversations/#{conv.conversation_id}/restore")

      assert %{"ok" => true} = json_response(conn, 200)

      # Verify deleted_at is now nil
      updated = App.Repo.get_by!(App.Projections.ConversationProjection,
        conversation_id: conv.conversation_id)
      assert is_nil(updated.deleted_at)
    end

    test "also works on an already-active conversation (idempotent restore)", %{conn: conn} do
      user = user_fixture()
      conv = conversation_fixture(user)

      conn =
        conn
        |> authed_conn(user)
        |> put("/api/conversations/#{conv.conversation_id}/restore")

      # The controller just sets deleted_at: nil regardless — should still succeed
      assert %{"ok" => true} = json_response(conn, 200)
    end

    test "returns 404 when conversation does not exist", %{conn: conn} do
      user = user_fixture()

      conn =
        conn
        |> authed_conn(user)
        |> put("/api/conversations/nonexistent-id/restore")

      assert %{"error" => _} = json_response(conn, 404)
    end

    test "returns 404 when conversation belongs to another user", %{conn: conn} do
      user = user_fixture()
      other_user = user_fixture()
      other_conv = deleted_conversation_fixture(other_user)

      conn =
        conn
        |> authed_conn(user)
        |> put("/api/conversations/#{other_conv.conversation_id}/restore")

      assert %{"error" => _} = json_response(conn, 404)
    end

    test "returns 401 without authentication", %{conn: conn} do
      user = user_fixture()
      conv = deleted_conversation_fixture(user)

      conn = put(conn, "/api/conversations/#{conv.conversation_id}/restore")
      assert conn.status == 401
    end
  end
end
