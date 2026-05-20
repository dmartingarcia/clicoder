defmodule AppWeb.Admin.AdminLayout do
  use AppWeb, :html

  def render("admin.html", assigns) do
    ~H"""
    <!DOCTYPE html>
    <html lang="es">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Backoffice — CIE-10</title>
        <link rel="stylesheet" href={~p"/assets/app.css"} />
        <script defer src={~p"/assets/app.js"}></script>
      </head>
      <body class="bg-gray-100 min-h-screen">
        <nav class="bg-indigo-700 text-white px-6 py-3 flex items-center justify-between shadow">
          <div class="flex items-center gap-6">
            <span class="font-bold text-lg">CIE-10 Backoffice</span>
            <.link navigate={~p"/admin/users"} class="text-indigo-200 hover:text-white text-sm">
              Usuarios
            </.link>
          </div>
          <.link
            href={~p"/admin/logout"}
            method="delete"
            class="text-indigo-200 hover:text-white text-sm"
          >
            Cerrar sesión
          </.link>
        </nav>
        <main>
          {@inner_content}
        </main>
      </body>
    </html>
    """
  end
end
