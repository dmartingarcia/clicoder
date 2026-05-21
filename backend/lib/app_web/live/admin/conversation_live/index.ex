defmodule AppWeb.Admin.ConversationLive.Index do
  use AppWeb, :live_view

  alias App.Repo
  alias App.Projections.ConversationProjection
  alias App.Accounts.User
  import Ecto.Query

  @impl true
  def mount(_params, _session, socket) do
    conversations =
      Repo.all(
        from c in ConversationProjection,
          order_by: [desc: c.inserted_at],
          limit: 200
      )

    user_ids = conversations |> Enum.map(& &1.user_id) |> Enum.uniq()

    users_by_id =
      Repo.all(from u in User, where: u.id in ^user_ids)
      |> Map.new(&{to_string(&1.id), &1})

    {:ok, assign(socket, conversations: conversations, users_by_id: users_by_id)}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <div class="p-6">
      <h1 class="text-2xl font-bold text-gray-800 mb-6">
        Conversaciones (<%= length(@conversations) %>)
      </h1>

      <div class="bg-white rounded-lg shadow overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Usuario</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Estado</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Inicio</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Eliminada</th>
              <th></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <%= for conv <- @conversations do %>
              <% user = Map.get(@users_by_id, conv.user_id) %>
              <tr class="hover:bg-gray-50">
                <td class="px-4 py-3 text-xs font-mono text-gray-500">
                  <%= String.slice(conv.conversation_id, 0, 8) %>…
                </td>
                <td class="px-4 py-3 text-sm text-gray-700">
                  <%= if user do %>
                    <.link navigate={~p"/admin/users/#{user.id}"} class="text-indigo-600 hover:text-indigo-800">
                      <%= user.username %>
                    </.link>
                  <% else %>
                    <span class="text-gray-400 text-xs"><%= conv.user_id %></span>
                  <% end %>
                </td>
                <td class="px-4 py-3">
                  <span class={[
                    "px-2 py-1 rounded text-xs font-medium",
                    if(conv.deleted_at, do: "bg-red-100 text-red-700", else: "bg-green-100 text-green-700")
                  ]}>
                    <%= if conv.deleted_at, do: "Eliminada", else: conv.status %>
                  </span>
                </td>
                <td class="px-4 py-3 text-sm text-gray-600">
                  <%= Calendar.strftime(conv.inserted_at, "%d/%m/%Y %H:%M") %>
                </td>
                <td class="px-4 py-3 text-sm text-gray-500">
                  <%= if conv.deleted_at, do: Calendar.strftime(conv.deleted_at, "%d/%m/%Y"), else: "—" %>
                </td>
                <td class="px-4 py-3 text-right">
                  <.link
                    navigate={~p"/admin/conversations/#{conv.conversation_id}"}
                    class="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                  >
                    Ver →
                  </.link>
                </td>
              </tr>
            <% end %>
          </tbody>
        </table>
      </div>
    </div>
    """
  end
end
