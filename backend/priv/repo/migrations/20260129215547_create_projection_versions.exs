defmodule App.Repo.Migrations.CreateProjectionVersions do
  use Ecto.Migration

  def change do
    create table(:projection_versions, primary_key: false) do
      add :projection_name, :string, primary_key: true
      add :last_seen_event_number, :bigint, null: false, default: 0

      timestamps()
    end
  end
end
