defmodule App.Repo.Migrations.CreateSettings do
  use Ecto.Migration

  def change do
    create table(:settings, primary_key: false) do
      add :id, :binary_id, primary_key: true, default: fragment("gen_random_uuid()")
      add :summarizer_model, :string, null: false, default: "none"
      add :summarizer_mode, :string, null: false, default: "summary"
      add :prompt_summary, :text
      add :prompt_paraphrase, :text
      add :user_prompt_summary, :text
      add :user_prompt_paraphrase, :text

      timestamps(type: :utc_datetime)
    end
  end
end
