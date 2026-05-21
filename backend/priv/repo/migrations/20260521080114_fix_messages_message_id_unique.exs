defmodule App.Repo.Migrations.FixMessagesMessageIdUnique do
  use Ecto.Migration

  def change do
    drop index(:messages, [:message_id])
    create unique_index(:messages, [:message_id])
  end
end
