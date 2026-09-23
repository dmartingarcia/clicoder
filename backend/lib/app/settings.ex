defmodule App.Settings do
  @moduledoc """
  Persistencia en BD de la configuración del summarizer LLM y feature flags.

  Mantiene una única fila en la tabla `settings`. Si no existe, `load/0` devuelve `nil`
  y `SummarizerSettings` usa sus defaults. En cada cambio, `save/1` hace upsert.
  """

  use Ecto.Schema
  import Ecto.Changeset
  import Ecto.Query

  alias App.Repo

  @primary_key {:id, :binary_id, autogenerate: true}

  schema "settings" do
    field :summarizer_model, :string
    field :summarizer_mode, :string
    field :prompt_summary, :string
    field :prompt_paraphrase, :string
    field :user_prompt_summary, :string
    field :user_prompt_paraphrase, :string
    field :explain_method, :string

    timestamps(type: :utc_datetime)
  end

  @fields ~w(summarizer_model summarizer_mode prompt_summary prompt_paraphrase user_prompt_summary user_prompt_paraphrase explain_method)a

  def changeset(settings, attrs) do
    settings
    |> cast(attrs, @fields)
    |> validate_required([:summarizer_model, :summarizer_mode])
  end

  @spec load() :: %__MODULE__{} | nil
  def load do
    Repo.one(from s in __MODULE__, limit: 1)
  end

  @spec save(map()) :: {:ok, %__MODULE__{}} | {:error, Ecto.Changeset.t()}
  def save(attrs) do
    case load() do
      nil ->
        %__MODULE__{}
        |> changeset(attrs)
        |> Repo.insert()

      existing ->
        existing
        |> changeset(attrs)
        |> Repo.update()
    end
  end
end
