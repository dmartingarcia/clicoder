defmodule App.Repo.Migrations.AddExplainMethodToSettings do
  use Ecto.Migration

  # El motor de analisis se deja fuera a proposito: es volatil por diseno, sirve para comparar
  # motores durante la evaluacion y vuelve a su valor por defecto en cada arranque. El metodo de
  # atribucion no es un experimento sino una eleccion de calidad y coste, y debe sobrevivir a un
  # reinicio para que el sistema no cambie de comportamiento sin que nadie lo haya tocado.
  def change do
    alter table(:settings) do
      add :explain_method, :string
    end
  end
end
