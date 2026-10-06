defmodule App.Repo.Migrations.MessagesContentNullable do
  use Ecto.Migration

  # El informe clinico ya no viaja en los eventos (art. 9 RGPD, registro inmutable): el canal escribe
  # el texto despues de que el proyector cree la fila, asi que la columna no puede ser NOT NULL.
  def up, do: alter(table(:messages), do: modify(:content, :text, null: true))

  def down, do: alter(table(:messages), do: modify(:content, :text, null: false))
end
