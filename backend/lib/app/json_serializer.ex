defmodule App.JsonSerializer do
  @moduledoc """
  Custom EventStore serializer that uses `keys: :atoms` (instead of the default
  `keys: :atoms!`) so that nested JSON keys in stored events (e.g. `confidence`,
  `description`, `reason` inside AI prediction cards) don't crash deserialization
  when those atoms haven't been pre-loaded into the atom table.
  """

  @behaviour EventStore.Serializer

  def serialize(term) do
    Jason.encode!(term)
  end

  def deserialize(data, config) do
    decoded = Jason.decode!(data, keys: :atoms)

    case Keyword.fetch(config, :type) do
      {:ok, type} ->
        module = String.to_existing_atom(type)
        if is_map(decoded), do: struct(module, decoded), else: decoded

      :error ->
        # Called for event metadata — just return the decoded value as-is
        decoded
    end
  end
end
