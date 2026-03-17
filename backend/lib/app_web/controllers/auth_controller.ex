defmodule AppWeb.AuthController do
  use AppWeb, :controller

  alias App.Accounts
  alias App.Translations

  def register(conn, params) do
    locale = conn.assigns[:locale] || "es"
    attrs = params |> Map.take(["first_name", "last_name", "username", "email", "password"]) |> Map.put("locale", locale)

    case Accounts.register_user(attrs) do
      {:ok, user} ->
        conn
        |> put_status(:created)
        |> json(%{
          status: "pending_confirmation",
          message: Translations.t(locale, "auth.check_email_body", email: user.email),
          user: %{email: user.email}
        })

      {:error, changeset} ->
        errors = Ecto.Changeset.traverse_errors(changeset, fn {msg, _opts} -> msg end)

        conn
        |> put_status(:unprocessable_entity)
        |> json(%{errors: errors})
    end
  end

  def login(conn, %{"email" => email, "password" => password}) do
    locale = conn.assigns[:locale] || "es"

    case Accounts.authenticate(email, password) do
      {:ok, user} ->
        token = Phoenix.Token.sign(AppWeb.Endpoint, "user auth", user.id)
        json(conn, %{token: token, user: format_user(user)})

      {:error, :email_not_confirmed} ->
        conn
        |> put_status(:forbidden)
        |> json(%{error: Translations.t(locale, "auth.error_not_confirmed")})

      {:error, :invalid_credentials} ->
        conn
        |> put_status(:unauthorized)
        |> json(%{error: Translations.t(locale, "auth.error_invalid_credentials")})
    end
  end

  def confirm(conn, %{"token" => token}) do
    case Accounts.confirm_user(token) do
      {:ok, user} ->
        auth_token = Phoenix.Token.sign(AppWeb.Endpoint, "user auth", user.id)
        frontend_url = System.get_env("FRONTEND_URL") || "http://localhost:3000"
        redirect(conn, external: "#{frontend_url}?confirmed=1&token=#{auth_token}&user_id=#{user.id}")

      {:error, :invalid_token} ->
        conn
        |> put_status(:not_found)
        |> json(%{error: "Token inválido o ya utilizado"})
    end
  end

  def update_locale(conn, %{"locale" => locale}) do
    user_id = conn.assigns[:current_user_id]

    case Accounts.update_locale(user_id, locale) do
      {:ok, user} -> json(conn, %{locale: user.locale})
      {:error, _} -> conn |> put_status(:unprocessable_entity) |> json(%{error: "Invalid locale"})
    end
  end

  defp format_user(user) do
    %{
      id: user.id,
      first_name: user.first_name,
      last_name: user.last_name,
      username: user.username,
      email: user.email,
      locale: user.locale
    }
  end
end
