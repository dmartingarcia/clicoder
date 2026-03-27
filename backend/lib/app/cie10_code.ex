defmodule App.Cie10Code do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, :binary_id, autogenerate: true}

  @types ~w(diagnosis procedure chemical)

  schema "cie10_codes" do
    field :code, :string
    field :description, :string
    field :type, :string
    field :metadata, :map

    timestamps(type: :utc_datetime)
  end

  def changeset(struct, attrs) do
    struct
    |> cast(attrs, [:code, :description, :type, :metadata])
    |> validate_required([:code, :description, :type])
    |> validate_inclusion(:type, @types)
    |> unique_constraint(:code)
  end
end
