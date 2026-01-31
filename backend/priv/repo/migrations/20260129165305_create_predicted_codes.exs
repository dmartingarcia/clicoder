defmodule App.Repo.Migrations.CreatePredictedCodes do
  use Ecto.Migration

  def change do
    create table(:predicted_codes, primary_key: false) do
      add :id, :binary_id, primary_key: true
      add :code_id, :string, null: false
      add :cie10_code, :string, null: false
      add :reasoning, :text
      add :confidence_score, :float
      add :status, :string, default: "pending"
      add :validated_by, :string
      add :rejected_by, :string
      add :rejection_reason, :text
      add :conversation_id, references(:conversations, type: :binary_id, on_delete: :delete_all)

      timestamps(type: :utc_datetime)
    end

    create index(:predicted_codes, [:conversation_id])
    create index(:predicted_codes, [:code_id])
    create index(:predicted_codes, [:cie10_code])
    create index(:predicted_codes, [:status])
  end
end
