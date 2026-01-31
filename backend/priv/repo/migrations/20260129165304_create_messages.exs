defmodule App.Repo.Migrations.CreateMessages do
  use Ecto.Migration

  def change do
    create table(:messages, primary_key: false) do
      add :id, :binary_id, primary_key: true
      add :message_id, :string, null: false
      add :content, :text, null: false
      add :user_id, :string, null: false
      add :timestamp, :utc_datetime, null: false
      add :message_type, :string, null: false
      add :conversation_id, references(:conversations, type: :binary_id, on_delete: :delete_all)

      timestamps(type: :utc_datetime)
    end

    create index(:messages, [:conversation_id])
    create index(:messages, [:message_id])
    create index(:messages, [:timestamp])
  end
end
