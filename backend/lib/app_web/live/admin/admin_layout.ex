defmodule AppWeb.Admin.AdminLayout do
  use Phoenix.Component

  import Phoenix.VerifiedRoutes, only: []

  def admin(assigns) do
    ~H"""
    <!DOCTYPE html>
    <html lang="es">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="csrf-token" content={Plug.CSRFProtection.get_csrf_token()} />
        <title>Backoffice — CIE-10</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script type="importmap">
          {
            "imports": {
              "phoenix": "/js/phoenix/phoenix.mjs",
              "phoenix_live_view": "/js/lv/phoenix_live_view.esm.js"
            }
          }
        </script>
        <script type="module">
          import {Socket} from "phoenix"
          import {LiveSocket} from "phoenix_live_view"
          let csrfToken = document.querySelector("meta[name='csrf-token']").getAttribute("content")
          let liveSocket = new LiveSocket("/live", Socket, {params: {_csrf_token: csrfToken}})
          liveSocket.connect()
        </script>
      </head>
      <body class="bg-gray-200 min-h-screen">
        <nav class="bg-indigo-700 text-white px-6 py-3 flex items-center justify-between shadow">
          <div class="flex items-center gap-6">
            <span class="font-bold text-lg">CIE-10 Backoffice</span>
            <a href="/admin/users" class="text-indigo-200 hover:text-white text-sm">Usuarios</a>
            <a href="/admin/conversations" class="text-indigo-200 hover:text-white text-sm">Conversaciones</a>
            <a href="/admin/settings" class="text-indigo-200 hover:text-white text-sm">Configuración</a>
          </div>
          <form action="/admin/logout" method="post">
            <input type="hidden" name="_method" value="delete" />
            <input type="hidden" name="_csrf_token" value={Plug.CSRFProtection.get_csrf_token()} />
            <button type="submit" class="text-indigo-200 hover:text-white text-sm cursor-pointer bg-transparent border-0 p-0">
              Cerrar sesión
            </button>
          </form>
        </nav>
        <main>
          {@inner_content}
        </main>
      </body>
    </html>
    """
  end
end
