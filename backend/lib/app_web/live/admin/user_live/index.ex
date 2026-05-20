defmodule AppWeb.Admin.UserLive.Index do
  use AppWeb, :live_view

  alias App.Repo
  alias App.Accounts.User
  import Ecto.Query

  @impl true
  def mount(_params, _session, socket) do
    users = Repo.all(from u in User, order_by: [desc: u.inserted_at])
    {:ok, assign(socket, :users, users)}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <div class="p-6">
      <h1 class="text-2xl font-bold text-gray-800 mb-6">Usuarios</h1>

      <div class="bg-white rounded-lg shadow overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Usuario</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Admin</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Confirmado</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Registro</th>
              <th></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <%= for user <- @users do %>
              <tr class="hover:bg-gray-50">
                <td class="px-4 py-3 text-sm font-medium text-gray-900"><%= user.username %></td>
                <td class="px-4 py-3 text-sm text-gray-600"><%= user.email %></td>
                <td class="px-4 py-3">
                  <%= if user.is_admin do %>
                    <span class="px-2 py-1 bg-indigo-100 text-indigo-700 rounded text-xs font-medium">Admin</span>
                  <% end %>
                </td>
                <td class="px-4 py-3">
                  <%= if user.confirmed_at do %>
                    <span class="px-2 py-1 bg-green-100 text-green-700 rounded text-xs">Sí</span>
                  <% else %>
                    <span class="px-2 py-1 bg-yellow-100 text-yellow-700 rounded text-xs">Pendiente</span>
                  <% end %>
                </td>
                <td class="px-4 py-3 text-sm text-gray-500">
                  <%= Calendar.strftime(user.inserted_at, "%d/%m/%Y") %>
                </td>
                <td class="px-4 py-3 text-right">
                  <.link navigate={~p"/admin/users/#{user.id}"} class="text-indigo-600 hover:text-indigo-800 text-sm font-medium">
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
