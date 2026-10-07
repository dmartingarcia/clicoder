defmodule AppWeb.ConversationControllerTest do
  use AppWeb.ConnCase, async: true

  import App.Fixtures

  defp authed_conn(conn, user) do
    {header_name, header_value} = auth_header(user)
    put_req_header(conn, header_name, header_value)
  end

  describe "index/2: active conversations" do
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

    test "lists the authenticated user's conversations when no user_id is sent", %{conn: conn} do
      user = user_fixture()
      propia = conversation_fixture(user)

      conn =
        conn
        |> authed_conn(user)
        |> get("/api/conversations")

      assert %{"conversations" => list} = json_response(conn, 200)
      assert Enum.map(list, & &1["conversation_id"]) == [propia.conversation_id]
    end

    test "returns 403 when asking for another user's conversations", %{conn: conn} do
      user = user_fixture()
      otro = user_fixture()
      _ajena = conversation_fixture(otro)

      conn =
        conn
        |> authed_conn(user)
        |> get("/api/conversations", %{"user_id" => otro.id})

      assert %{"error" => _} = json_response(conn, 403)
    end

    test "returns 401 without authentication", %{conn: conn} do
      conn = get(conn, "/api/conversations", %{"user_id" => "some-id"})
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

  describe "trash/2: deleted conversations" do
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

    test "returns 403 when asking for another user's trash", %{conn: conn} do
      user = user_fixture()
      otro = user_fixture()

      conn =
        conn
        |> authed_conn(user)
        |> get("/api/conversations/trash", %{"user_id" => otro.id})

      assert %{"error" => _} = json_response(conn, 403)
    end

    test "returns 401 without authentication", %{conn: conn} do
      conn = get(conn, "/api/conversations/trash", %{"user_id" => "some-id"})
      assert conn.status == 401
    end
  end

  describe "delete/2: soft delete" do
    test "soft-deletes an active conversation owned by the user", %{conn: conn} do
      user = user_fixture()
      conv = conversation_fixture(user)

      conn =
        conn
        |> authed_conn(user)
        |> delete("/api/conversations/#{conv.conversation_id}")

      assert %{"ok" => true} = json_response(conn, 200)

      updated =
        App.Repo.get_by!(App.Projections.ConversationProjection,
          conversation_id: conv.conversation_id
        )

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

  describe "restore/2: restore from trash" do
    test "restores a soft-deleted conversation", %{conn: conn} do
      user = user_fixture()
      conv = deleted_conversation_fixture(user)

      conn =
        conn
        |> authed_conn(user)
        |> put("/api/conversations/#{conv.conversation_id}/restore")

      assert %{"ok" => true} = json_response(conn, 200)

      updated =
        App.Repo.get_by!(App.Projections.ConversationProjection,
          conversation_id: conv.conversation_id
        )

      assert is_nil(updated.deleted_at)
    end

    test "also works on an already-active conversation (idempotent restore)", %{conn: conn} do
      user = user_fixture()
      conv = conversation_fixture(user)

      conn =
        conn
        |> authed_conn(user)
        |> put("/api/conversations/#{conv.conversation_id}/restore")

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

  describe "purge/2: borrado permanente (RGPD Art. 17)" do
    test "borra la conversación y todo lo que cuelga de ella", %{conn: conn} do
      user = user_fixture()
      conv = deleted_conversation_fixture(user)

      %App.Projections.MessageProjection{
        message_id: UUID.uuid4(),
        conversation_id: conv.id,
        user_id: to_string(user.id),
        content: "dato clínico",
        message_type: "user",
        timestamp: DateTime.utc_now() |> DateTime.truncate(:second)
      }
      |> App.Repo.insert!()

      %App.Projections.PredictedCodeProjection{
        code_id: UUID.uuid4(),
        conversation_id: conv.id,
        cie10_code: "I10",
        reasoning: "hipertensión",
        confidence_score: 0.9,
        status: "pending"
      }
      |> App.Repo.insert!()

      conn =
        conn
        |> authed_conn(user)
        |> delete("/api/conversations/#{conv.conversation_id}/purge")

      assert %{"ok" => true} = json_response(conn, 200)

      # El borrado permanente tiene que llevarse los datos clínicos asociados, no solo la
      # fila de la conversación: si quedan huérfanos, el derecho de supresión no se cumple.
      refute App.Repo.get(App.Projections.ConversationProjection, conv.id)
      assert App.Repo.aggregate(App.Projections.MessageProjection, :count) == 0
      assert App.Repo.aggregate(App.Projections.PredictedCodeProjection, :count) == 0
    end

    test "no permite borrar la conversación de otro usuario", %{conn: conn} do
      duenyo = user_fixture()
      intruso = user_fixture()
      conv = conversation_fixture(duenyo)

      conn =
        conn
        |> authed_conn(intruso)
        |> delete("/api/conversations/#{conv.conversation_id}/purge")

      assert json_response(conn, 404)["error"]
      assert App.Repo.get(App.Projections.ConversationProjection, conv.id)
    end

    test "una conversación inexistente devuelve 404", %{conn: conn} do
      user = user_fixture()

      conn =
        conn
        |> authed_conn(user)
        |> delete("/api/conversations/#{UUID.uuid4()}/purge")

      assert json_response(conn, 404)["error"]
    end

    test "sin autenticación devuelve 401", %{conn: conn} do
      user = user_fixture()
      conv = conversation_fixture(user)

      assert conn
             |> delete("/api/conversations/#{conv.conversation_id}/purge")
             |> Map.fetch!(:status) == 401
    end
  end
end
