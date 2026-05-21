defmodule App.Repo.Migrations.AddPredictedCodesCompositeIndex do
  use Ecto.Migration

  def change do
    create index(:predicted_codes, [:conversation_id, :status])
  end
end
