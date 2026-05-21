defmodule AppWeb.Admin.ConversationLive.Show do
  use AppWeb, :live_view

  alias App.Repo
  alias App.Projections.ConversationProjection
  alias App.Projections.MessageProjection
  alias App.Projections.AnalysisCardProjection
  alias App.Accounts.User
  import Ecto.Query

  @impl true
  def mount(%{"id" => conversation_id}, _session, socket) do
    conv =
      Repo.one!(
        from c in ConversationProjection,
          where: c.conversation_id == ^conversation_id
      )

    user = Repo.get(User, conv.user_id)

    messages =
      Repo.all(
        from m in MessageProjection,
          where: m.conversation_id == ^conv.id,
          order_by: [asc: m.timestamp]
      )

    cards =
      Repo.all(
        from a in AnalysisCardProjection,
          where: a.conversation_id == ^conv.id,
          order_by: [asc: a.inserted_at]
      )

    {:ok,
     assign(socket,
       conv: conv,
       user: user,
       messages: messages,
       cards: cards
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <div class="p-6">
      <.link navigate={~p"/admin/conversations"} class="text-indigo-600 hover:text-indigo-800 text-sm mb-4 inline-block">
        ← Volver a conversaciones
      </.link>

      <%!-- Cabecera de la conversación --%>
      <div class="bg-white rounded-lg shadow p-6 mb-6">
        <h1 class="text-lg font-bold text-gray-800 font-mono mb-3"><%= @conv.conversation_id %></h1>
        <dl class="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt class="text-gray-500">Usuario</dt>
            <dd class="font-medium text-gray-800">
              <%= if @user do %>
                <.link navigate={~p"/admin/users/#{@user.id}"} class="text-indigo-600 hover:text-indigo-800">
                  <%= @user.username %>
                </.link>
              <% else %>
                <span class="text-gray-400"><%= @conv.user_id %></span>
              <% end %>
            </dd>
          </div>
          <div>
            <dt class="text-gray-500">Estado</dt>
            <dd>
              <span class={[
                "px-2 py-1 rounded text-xs font-medium",
                if(@conv.deleted_at, do: "bg-red-100 text-red-700", else: "bg-green-100 text-green-700")
              ]}>
                <%= if @conv.deleted_at, do: "Eliminada", else: @conv.status %>
              </span>
            </dd>
          </div>
          <div>
            <dt class="text-gray-500">Inicio</dt>
            <dd class="font-medium text-gray-800">
              <%= Calendar.strftime(@conv.inserted_at, "%d/%m/%Y %H:%M") %>
            </dd>
          </div>
          <%= if @conv.deleted_at do %>
            <div>
              <dt class="text-gray-500">Eliminada</dt>
              <dd class="font-medium text-gray-800">
                <%= Calendar.strftime(@conv.deleted_at, "%d/%m/%Y %H:%M") %>
              </dd>
            </div>
          <% end %>
        </dl>
      </div>

      <%!-- Mensajes --%>
      <h2 class="text-lg font-semibold text-gray-700 mb-3">
        Mensajes (<%= length(@messages) %>)
      </h2>

      <%= if Enum.empty?(@messages) do %>
        <p class="text-gray-400 text-sm mb-6">Sin mensajes.</p>
      <% else %>
        <div class="space-y-3 mb-6">
          <%= for msg <- @messages do %>
            <div class={[
              "rounded-lg p-4",
              case msg.message_type do
                "user" -> "bg-blue-50 border border-blue-100"
                "assistant" -> "bg-white border border-gray-200 shadow-sm"
                _ -> "bg-gray-50 border border-gray-200"
              end
            ]}>
              <div class="flex items-center justify-between mb-1">
                <span class="text-xs font-semibold text-gray-500 uppercase"><%= msg.message_type %></span>
                <span class="text-xs text-gray-400">
                  <%= Calendar.strftime(msg.timestamp, "%d/%m/%Y %H:%M") %>
                </span>
              </div>
              <p class="text-sm text-gray-800 whitespace-pre-wrap"><%= msg.content %></p>
            </div>
          <% end %>
        </div>
      <% end %>

      <%!-- Analysis Cards --%>
      <h2 class="text-lg font-semibold text-gray-700 mb-3">
        Analysis Cards (<%= length(@cards) %>)
      </h2>

      <%= if Enum.empty?(@cards) do %>
        <p class="text-gray-400 text-sm">Sin cards.</p>
      <% else %>
        <div class="bg-white rounded-lg shadow overflow-hidden">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Fecha</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tipo</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Engine</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Contenido</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <%= for card <- @cards do %>
                <tr class="hover:bg-gray-50">
                  <td class="px-4 py-3 text-sm text-gray-500"><%= Calendar.strftime(card.inserted_at, "%d/%m/%Y %H:%M") %></td>
                  <td class="px-4 py-3">
                    <span class="px-2 py-1 bg-indigo-100 text-indigo-700 rounded text-xs font-medium">
                      <%= card.card_type %>
                    </span>
                  </td>
                  <td class="px-4 py-3">
                    <%= if card.engine do %>
                      <span class="px-2 py-1 bg-amber-100 text-amber-700 rounded text-xs font-medium">
                        <%= card.engine %>
                      </span>
                    <% else %>
                      <span class="text-gray-400 text-xs">—</span>
                    <% end %>
                  </td>
                  <td class="px-4 py-3 text-sm text-gray-700 max-w-lg">
                    <p class="truncate"><%= card.content %></p>
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
