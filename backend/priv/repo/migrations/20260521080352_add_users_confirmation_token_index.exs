defmodule App.Repo.Migrations.AddUsersConfirmationTokenIndex do
  use Ecto.Migration

  def change do
    create index(:users, [:confirmation_token])
  end
end
