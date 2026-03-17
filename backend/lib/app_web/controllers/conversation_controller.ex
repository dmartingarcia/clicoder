defmodule AppWeb.ConversationController do
  use AppWeb, :controller

  alias App.Repo
  alias App.Projections.ConversationProjection

  import Ecto.Query

  # Active conversations (not deleted)
  def index(conn, %{"user_id" => user_id}) do
    conversations =
      ConversationProjection
      |> where([c], c.user_id == ^user_id and is_nil(c.deleted_at))
      |> order_by([c], desc: c.started_at)
      |> preload(:messages)
      |> Repo.all()
      |> Enum.map(&format_conversation/1)

    json(conn, %{conversations: conversations})
  end

  def index(conn, _params) do
    conn
    |> put_status(:bad_request)
    |> json(%{error: "user_id is required"})
  end

  # Trash: soft-deleted conversations
  def trash(conn, %{"user_id" => user_id}) do
    conversations =
      ConversationProjection
      |> where([c], c.user_id == ^user_id and not is_nil(c.deleted_at))
      |> order_by([c], desc: c.deleted_at)
      |> preload(:messages)
      |> Repo.all()
      |> Enum.map(&format_conversation/1)

    json(conn, %{conversations: conversations})
  end

  def trash(conn, _params) do
    conn
    |> put_status(:bad_request)
    |> json(%{error: "user_id is required"})
  end

  # Soft delete
  def delete(conn, %{"conversation_id" => conversation_id}) do
    user_id = conn.assigns.current_user_id

    case Repo.get_by(ConversationProjection, conversation_id: conversation_id, user_id: user_id) do
      nil ->
        conn |> put_status(:not_found) |> json(%{error: "Conversation not found"})

      conv ->
        conv
        |> Ecto.Changeset.change(deleted_at: DateTime.utc_now() |> DateTime.truncate(:second))
        |> Repo.update!()

        json(conn, %{ok: true})
    end
  end

  # Restore from trash
  def restore(conn, %{"conversation_id" => conversation_id}) do
    user_id = conn.assigns.current_user_id

    case Repo.get_by(ConversationProjection, conversation_id: conversation_id, user_id: user_id) do
      nil ->
        conn |> put_status(:not_found) |> json(%{error: "Conversation not found"})

      conv ->
        conv
        |> Ecto.Changeset.change(deleted_at: nil)
        |> Repo.update!()

        json(conn, %{ok: true})
    end
  end

  defp format_conversation(conv) do
    last_message =
      conv.messages
      |> Enum.sort_by(& &1.timestamp, {:desc, DateTime})
      |> List.first()

    %{
      conversation_id: conv.conversation_id,
      started_at: conv.started_at,
      status: conv.status,
      deleted_at: conv.deleted_at,
      message_count: length(conv.messages),
      last_message:
        last_message &&
          %{content: last_message.content, timestamp: last_message.timestamp}
    }
  end
end
