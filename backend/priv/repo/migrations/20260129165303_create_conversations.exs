defmodule App.Repo.Migrations.CreateConversations do
  use Ecto.Migration

  def change do
    create table(:conversations, primary_key: false) do
      add :id, :binary_id, primary_key: true
      add :conversation_id, :string, null: false
      add :user_id, :string, null: false
      add :started_at, :utc_datetime, null: false
      add :status, :string, default: "active"

      timestamps(type: :utc_datetime)
    end

    create unique_index(:conversations, [:conversation_id])
    create index(:conversations, [:user_id])
  end
end
