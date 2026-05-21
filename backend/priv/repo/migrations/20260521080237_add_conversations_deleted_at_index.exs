defmodule App.Repo.Migrations.AddConversationsDeletedAtIndex do
  use Ecto.Migration

  def change do
    create index(:conversations, [:deleted_at], where: "deleted_at IS NOT NULL")
  end
end
