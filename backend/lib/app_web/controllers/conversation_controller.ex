defmodule AppWeb.ConversationController do
  use AppWeb, :controller
  use OpenApiSpex.ControllerSpecs

  alias App.Repo
  alias App.Projections.ConversationProjection
  alias App.Projections.MessageProjection
  alias App.Projections.AnalysisCardProjection
  alias App.Projections.PredictedCodeProjection
  alias App.Projections.CodeSuggestionProjection

  import Ecto.Query

  operation(:index,
    summary: "Listar conversaciones activas",
    tags: ["Conversations"],
    security: [%{"bearer_auth" => []}],
    parameters: [
      OpenApiSpex.Operation.parameter(:user_id, :query, :string, "ID del usuario", required: true)
    ],
    responses: [
      ok:
        {"Lista de conversaciones", "application/json",
         %OpenApiSpex.Schema{
           type: :object,
           properties: %{
             conversations: %OpenApiSpex.Schema{
               type: :array,
               items: %OpenApiSpex.Schema{type: :object}
             }
           }
         }}
    ]
  )

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

  operation(:trash,
    summary: "Conversaciones en papelera",
    tags: ["Conversations"],
    security: [%{"bearer_auth" => []}],
    parameters: [
      OpenApiSpex.Operation.parameter(:user_id, :query, :string, "ID del usuario", required: true)
    ],
    responses: [
      ok:
        {"Conversaciones eliminadas", "application/json",
         %OpenApiSpex.Schema{
           type: :object,
           properties: %{
             conversations: %OpenApiSpex.Schema{
               type: :array,
               items: %OpenApiSpex.Schema{type: :object}
             }
           }
         }}
    ]
  )

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

  operation(:delete,
    summary: "Mover conversación a papelera",
    tags: ["Conversations"],
    security: [%{"bearer_auth" => []}],
    parameters: [
      OpenApiSpex.Operation.parameter(:conversation_id, :path, :string, "ID de la conversación",
        required: true
      )
    ],
    responses: [
      ok:
        {"Eliminada", "application/json",
         %OpenApiSpex.Schema{
           type: :object,
           properties: %{ok: %OpenApiSpex.Schema{type: :boolean}}
         }},
      not_found:
        {"No encontrada", "application/json",
         %OpenApiSpex.Schema{
           type: :object,
           properties: %{error: %OpenApiSpex.Schema{type: :string}}
         }}
    ]
  )

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

  operation(:restore,
    summary: "Restaurar conversación de la papelera",
    tags: ["Conversations"],
    security: [%{"bearer_auth" => []}],
    parameters: [
      OpenApiSpex.Operation.parameter(:conversation_id, :path, :string, "ID de la conversación",
        required: true
      )
    ],
    responses: [
      ok:
        {"Restaurada", "application/json",
         %OpenApiSpex.Schema{
           type: :object,
           properties: %{ok: %OpenApiSpex.Schema{type: :boolean}}
         }},
      not_found:
        {"No encontrada", "application/json",
         %OpenApiSpex.Schema{
           type: :object,
           properties: %{error: %OpenApiSpex.Schema{type: :string}}
         }}
    ]
  )

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

  operation(:purge,
    summary: "Eliminar conversación permanentemente (RGPD Art. 17)",
    tags: ["Conversations"],
    security: [%{"bearer_auth" => []}],
    parameters: [
      OpenApiSpex.Operation.parameter(:conversation_id, :path, :string, "ID de la conversación",
        required: true
      )
    ],
    responses: [
      ok:
        {"Eliminada permanentemente", "application/json",
         %OpenApiSpex.Schema{
           type: :object,
           properties: %{ok: %OpenApiSpex.Schema{type: :boolean}}
         }},
      not_found:
        {"No encontrada", "application/json",
         %OpenApiSpex.Schema{
           type: :object,
           properties: %{error: %OpenApiSpex.Schema{type: :string}}
         }}
    ]
  )

  # Hard delete: borra todos los datos de la conversación (RGPD Art. 17)
  def purge(conn, %{"conversation_id" => conversation_id}) do
    user_id = conn.assigns.current_user_id

    case Repo.get_by(ConversationProjection, conversation_id: conversation_id, user_id: user_id) do
      nil ->
        conn |> put_status(:not_found) |> json(%{error: "Conversation not found"})

      conv ->
        Repo.transaction(fn ->
          from(r in CodeSuggestionProjection, where: r.conversation_id == ^conv.id)
          |> Repo.delete_all()

          from(r in PredictedCodeProjection, where: r.conversation_id == ^conv.id)
          |> Repo.delete_all()

          from(r in AnalysisCardProjection, where: r.conversation_id == ^conv.id)
          |> Repo.delete_all()

          from(r in MessageProjection, where: r.conversation_id == ^conv.id) |> Repo.delete_all()
          Repo.delete!(conv)
        end)

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
