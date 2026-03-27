defmodule App.Repo.Migrations.CreateCie10Codes do
  use Ecto.Migration

  def change do
    create table(:cie10_codes, primary_key: false) do
      add :id, :binary_id, primary_key: true
      add :code, :string, null: false
      add :description, :text, null: false
      add :type, :string, null: false
      add :metadata, :map

      timestamps(type: :utc_datetime)
    end

    create unique_index(:cie10_codes, [:code])
    create index(:cie10_codes, [:type])
  end
end
