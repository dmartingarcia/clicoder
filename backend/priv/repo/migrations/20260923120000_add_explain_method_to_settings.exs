defmodule App.Repo.Migrations.AddExplainMethodToSettings do
  use Ecto.Migration

  # El motor de analisis queda fuera a proposito: es volatil y vuelve a su valor por defecto en cada
  # arranque; el metodo de atribucion es una eleccion de calidad y coste y debe sobrevivir a un reinicio.
  def change do
    alter table(:settings) do
      add :explain_method, :string
    end
  end
end
