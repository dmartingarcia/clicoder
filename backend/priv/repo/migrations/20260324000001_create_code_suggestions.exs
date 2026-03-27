defmodule App.Repo.Migrations.CreateCodeSuggestions do
  use Ecto.Migration

  def change do
    create table(:code_suggestions, primary_key: false) do
      add :id, :binary_id, primary_key: true
      add :suggestion_id, :string, null: false
      add :conversation_id, references(:conversations, type: :binary_id, on_delete: :delete_all)
      add :selected_text, :string, null: false
      add :suggested_code, :string, null: false
      add :suggested_by, :string, null: false

      timestamps(type: :utc_datetime)
    end

    create unique_index(:code_suggestions, [:suggestion_id])
    create index(:code_suggestions, [:conversation_id])
  end
end
