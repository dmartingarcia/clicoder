defmodule App.Repo.Migrations.AddEngineToAnalysisCards do
  use Ecto.Migration

  def change do
    alter table(:analysis_cards) do
      add :engine, :string
    end
  end
end
