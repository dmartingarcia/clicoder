defmodule App.Repo.Migrations.AddDeletedAtToConversations do
  use Ecto.Migration

  def change do
    alter table(:conversations) do
      add :deleted_at, :utc_datetime, null: true
    end
  end
end
