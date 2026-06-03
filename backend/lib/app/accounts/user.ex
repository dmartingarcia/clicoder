defmodule App.Accounts.User do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, :binary_id, autogenerate: true}

  schema "users" do
    field :first_name, :string
    field :last_name, :string
    field :username, :string
    field :email, :string
    field :password_hash, :string
    field :password, :string, virtual: true
    field :locale, :string, default: "es"
    field :confirmation_token, :string
    field :confirmed_at, :utc_datetime
    field :is_admin, :boolean, default: false

    timestamps(type: :utc_datetime)
  end

  def registration_changeset(user, attrs) do
    user
    |> cast(attrs, [:first_name, :last_name, :username, :email, :password, :locale])
    |> validate_required([:first_name, :last_name, :username, :email, :password])
    |> validate_format(:email, ~r/^[^\s]+@[^\s]+$/, message: "formato de email inválido")
    |> validate_format(:username, ~r/^[a-zA-Z0-9_]+$/,
      message: "solo letras, números y guión bajo"
    )
    |> validate_length(:username, min: 3, message: "mínimo 3 caracteres")
    |> validate_length(:password, min: 12, message: "mínimo 12 caracteres")
    |> unique_constraint(:email, message: "email ya registrado")
    |> unique_constraint(:username, message: "nombre de usuario no disponible")
    |> hash_password()
    |> put_change(
      :confirmation_token,
      :crypto.strong_rand_bytes(32) |> Base.url_encode64(padding: false)
    )
  end

  def confirm_changeset(user) do
    change(user,
      confirmed_at: DateTime.utc_now() |> DateTime.truncate(:second),
      confirmation_token: nil
    )
  end

  defp hash_password(%{valid?: false} = changeset), do: changeset

  defp hash_password(changeset) do
    password = get_change(changeset, :password)
    put_change(changeset, :password_hash, Bcrypt.hash_pwd_salt(password))
  end
end
