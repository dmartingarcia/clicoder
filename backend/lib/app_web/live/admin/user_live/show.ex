defmodule AppWeb.Admin.UserLive.Show do
  use AppWeb, :live_view

  alias App.Repo
  alias App.Accounts.User
  alias App.Projections.ConversationProjection
  import Ecto.Query

  @impl true
  def mount(%{"id" => id}, _session, socket) do
    user = Repo.get!(User, id)

    conversations =
      Repo.all(
        from c in ConversationProjection,
          where: c.user_id == ^id,
          order_by: [desc: c.inserted_at]
      )

    {:ok, assign(socket, user: user, conversations: conversations)}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <div class="p-6">
      <.link navigate={~p"/admin/users"} class="text-indigo-600 hover:text-indigo-800 text-sm mb-4 inline-block">
        ← Volver a usuarios
      </.link>

      <div class="bg-white rounded-lg shadow p-6 mb-6">
        <div class="flex items-center justify-between mb-4">
          <h1 class="text-2xl font-bold text-gray-800"><%= @user.first_name %> <%= @user.last_name %></h1>
          <%= if @user.is_admin do %>
            <span class="px-3 py-1 bg-indigo-100 text-indigo-700 rounded-full text-sm font-medium">Admin</span>
          <% end %>
        </div>
        <dl class="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt class="text-gray-500">Username</dt>
            <dd class="font-medium text-gray-800"><%= @user.username %></dd>
          </div>
          <div>
            <dt class="text-gray-500">Email</dt>
            <dd class="font-medium text-gray-800"><%= @user.email %></dd>
          </div>
          <div>
            <dt class="text-gray-500">Idioma</dt>
            <dd class="font-medium text-gray-800"><%= @user.locale %></dd>
          </div>
          <div>
            <dt class="text-gray-500">Confirmado</dt>
            <dd class="font-medium text-gray-800">
              <%= if @user.confirmed_at,
                do: Calendar.strftime(@user.confirmed_at, "%d/%m/%Y %H:%M"),
                else: "Pendiente" %>
            </dd>
          </div>
          <div>
            <dt class="text-gray-500">Registro</dt>
            <dd class="font-medium text-gray-800">
              <%= Calendar.strftime(@user.inserted_at, "%d/%m/%Y %H:%M") %>
            </dd>
          </div>
        </dl>
      </div>

      <h2 class="text-lg font-semibold text-gray-700 mb-3">
        Conversaciones (<%= length(@conversations) %>)
      </h2>

      <%= if Enum.empty?(@conversations) do %>
        <p class="text-gray-400 text-sm">Sin conversaciones.</p>
      <% else %>
        <div class="bg-white rounded-lg shadow overflow-hidden">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID conversación</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Estado</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Inicio</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Eliminada</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <%= for conv <- @conversations do %>
                <tr class="hover:bg-gray-50">
                  <td class="px-4 py-3 text-xs font-mono text-gray-600">
                    <.link navigate={~p"/admin/conversations/#{conv.conversation_id}"} class="text-indigo-600 hover:text-indigo-800">
                      <%= String.slice(conv.conversation_id, 0, 8) %>…
                    </.link>
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
                </tr>
              <% end %>
            </tbody>
          </table>
        </div>
      <% end %>
    </div>
    """
  end
end
