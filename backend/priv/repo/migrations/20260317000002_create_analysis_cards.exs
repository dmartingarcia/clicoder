defmodule App.Repo.Migrations.CreateAnalysisCards do
  use Ecto.Migration

  def change do
    create table(:analysis_cards, primary_key: false) do
      add :id, :binary_id, primary_key: true
      add :card_id, :string, null: false
      add :card_type, :string, null: false
      add :content, :text, null: false
      add :position, :integer, null: false, default: 0
      add :message_id, :string, null: false
      add :conversation_id, references(:conversations, type: :binary_id, on_delete: :delete_all)

      timestamps(type: :utc_datetime)
    end

    create unique_index(:analysis_cards, [:card_id])
    create index(:analysis_cards, [:conversation_id])
    create index(:analysis_cards, [:message_id])
  end
end
