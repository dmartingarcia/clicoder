defmodule App.Accounts do
  alias App.Repo
  alias App.Accounts.{User, Emails}

  def register_user(attrs) do
    case %User{} |> User.registration_changeset(attrs) |> Repo.insert() do
      {:ok, user} ->
        Task.start(fn -> Emails.send_confirmation(user) end)
        {:ok, user}

      {:error, changeset} ->
        {:error, changeset}
    end
  end

  def confirm_user(token) do
    case Repo.get_by(User, confirmation_token: token) do
      nil ->
        {:error, :invalid_token}

      user ->
        user
        |> User.confirm_changeset()
        |> Repo.update()
    end
  end

  def get_user_by_email(email) do
    Repo.get_by(User, email: email)
  end

  def get_user(id), do: Repo.get(User, id)

  # Los idiomas que la interfaz sabe servir. Guardar cualquier otro no falla en el momento,
  # pero deja al usuario con una interfaz que cae al idioma por defecto y con los correos en
  # un idioma que nadie eligió, así que se rechaza al entrar en vez de degradar en silencio.
  @idiomas_admitidos ~w(es en fr it de)

  @doc "Idiomas admitidos por la interfaz."
  def idiomas_admitidos, do: @idiomas_admitidos

  def update_locale(_user_id, locale) when locale not in @idiomas_admitidos do
    {:error, :unsupported_locale}
  end

  def update_locale(user_id, locale) do
    case get_user(user_id) do
      nil ->
        {:error, :not_found}

      user ->
        user
        |> Ecto.Changeset.change(locale: locale)
        |> Repo.update()
    end
  end

  def authenticate(email, password) do
    user = get_user_by_email(email)

    cond do
      is_nil(user) ->
        Bcrypt.no_user_verify()
        {:error, :invalid_credentials}

      is_nil(user.confirmed_at) ->
        {:error, :email_not_confirmed}

      Bcrypt.verify_pass(password, user.password_hash) ->
        {:ok, user}

      true ->
        {:error, :invalid_credentials}
    end
  end
end
