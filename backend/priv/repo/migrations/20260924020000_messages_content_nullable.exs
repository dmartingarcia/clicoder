defmodule App.Repo.Migrations.MessagesContentNullable do
  use Ecto.Migration

  # El informe clinico dejo de viajar en los eventos: es una categoria especial del articulo 9
  # del RGPD y el registro de eventos es inmutable, de modo que lo que entrase ahi no se podria
  # borrar nunca. Ahora el proyector materializa el hecho (quien, cuando, que conversacion) y el
  # texto lo escribe el canal sobre esa misma fila. Entre ambos momentos la columna esta vacia,
  # asi que no puede ser NOT NULL.
  def up, do: alter(table(:messages), do: modify(:content, :text, null: true))

  def down, do: alter(table(:messages), do: modify(:content, :text, null: false))
end
