defmodule App.Repo.Migrations.AddVerifiedTriggersToPredictedCodes do
  use Ecto.Migration

  def change do
    alter table(:predicted_codes) do
      add :verified_triggers, {:array, :string}, default: [], null: false
    end
  end
end
