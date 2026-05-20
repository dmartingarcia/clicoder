defmodule AppWeb.Cie10Controller do
  use AppWeb, :controller
  use OpenApiSpex.ControllerSpecs

  import Ecto.Query, only: [from: 2]
  alias App.Repo
  alias App.Cie10Code

  @max_results 20
  @default_results 10

  operation :search,
    summary: "Buscar códigos CIE-10",
    tags: ["CIE-10"],
    parameters: [
      OpenApiSpex.Operation.parameter(:q, :query, :string, "Texto a buscar (código o descripción)", required: true),
      OpenApiSpex.Operation.parameter(:limit, :query, :integer, "Número máximo de resultados (1-#{@max_results})", example: 10),
      OpenApiSpex.Operation.parameter(:type, :query, :string, "Filtrar por tipo",
        schema: %OpenApiSpex.Schema{type: :string, enum: ["diagnosis", "procedure", "chemical"]})
    ],
    responses: [
      ok: {"Resultados de búsqueda", "application/json",
       %OpenApiSpex.Schema{
         type: :object,
         properties: %{
           results: %OpenApiSpex.Schema{
             type: :array,
             items: %OpenApiSpex.Schema{
               type: :object,
               properties: %{
                 code: %OpenApiSpex.Schema{type: :string},
                 description: %OpenApiSpex.Schema{type: :string},
                 type: %OpenApiSpex.Schema{type: :string},
                 metadata: %OpenApiSpex.Schema{type: :object}
               }
             }
           }
         }
       }}
    ]

  # GET /api/cie10/search?q=<query>&limit=<n>&type=<diagnosis|procedure|chemical>
  def search(conn, %{"q" => q} = params) do
    q_trimmed = String.trim(q)

    if byte_size(q_trimmed) < 2 do
      json(conn, %{results: []})
    else
      limit = parse_limit(params["limit"])
      type_filter = params["type"]

      results = run_search(q_trimmed, limit, type_filter)
      json(conn, %{results: Enum.map(results, &format_result/1)})
    end
  end

  def search(conn, _params), do: json(conn, %{results: []})

  operation :show,
    summary: "Obtener código CIE-10",
    tags: ["CIE-10"],
    parameters: [
      OpenApiSpex.Operation.parameter(:code, :path, :string, "Código CIE-10", required: true, example: "J18.9")
    ],
    responses: [
      ok: {"Código encontrado", "application/json",
       %OpenApiSpex.Schema{type: :object, properties: %{result: %OpenApiSpex.Schema{type: :object}}}},
      not_found: {"Código no encontrado", "application/json",
       %OpenApiSpex.Schema{type: :object, properties: %{error: %OpenApiSpex.Schema{type: :string}}}}
    ]

  # GET /api/cie10/codes/:code
  def show(conn, %{"code" => code}) do
    case Repo.get_by(Cie10Code, code: String.upcase(code)) do
      nil ->
        conn
        |> put_status(:not_found)
        |> json(%{error: "Code not found"})

      entry ->
        json(conn, %{result: format_result(entry)})
    end
  end

  operation :children,
    summary: "Hijos de un código CIE-10",
    tags: ["CIE-10"],
    parameters: [
      OpenApiSpex.Operation.parameter(:code, :path, :string, "Código padre", required: true, example: "J18")
    ],
    responses: [
      ok: {"Lista de hijos", "application/json",
       %OpenApiSpex.Schema{
         type: :object,
         properties: %{
           children: %OpenApiSpex.Schema{type: :array, items: %OpenApiSpex.Schema{type: :object}},
           is_leaf: %OpenApiSpex.Schema{type: :boolean}
         }
       }}
    ]

  # GET /api/cie10/codes/:code/children
  def children(conn, %{"code" => code}) do
    prefix = String.upcase(code)
    like_pattern = "#{sanitize(prefix)}%"

    child_codes =
      from(c in Cie10Code,
        where: ilike(c.code, ^like_pattern) and c.code != ^prefix,
        select: c.code,
        order_by: c.code
      )
      |> Repo.all()

    if child_codes == [] do
      json(conn, %{children: [], is_leaf: true})
    else
      next_len =
        child_codes
        |> Enum.map(&String.length/1)
        |> Enum.min()

      child_prefixes =
        child_codes
        |> Enum.map(&String.slice(&1, 0, next_len))
        |> Enum.uniq()
        |> Enum.sort()

      existing =
        from(c in Cie10Code,
          where: c.code in ^child_prefixes,
          order_by: c.code
        )
        |> Repo.all()

      existing_map = Map.new(existing, &{&1.code, &1})

      children_result =
        Enum.map(child_prefixes, fn cp ->
          case Map.get(existing_map, cp) do
            nil -> %{code: cp, description: nil, type: nil, metadata: nil, is_virtual: true}
            entry -> entry |> format_result() |> Map.put(:is_virtual, false)
          end
        end)

      json(conn, %{children: children_result, is_leaf: false})
    end
  end

  defp run_search(q, limit, type_filter) do
    prefix = "#{sanitize(q)}%"
    anywhere = "%#{sanitize(q)}%"

    base =
      from c in Cie10Code,
        where: ilike(c.code, ^prefix) or ilike(c.description, ^anywhere),
        order_by: [
          asc: fragment("CASE WHEN ? ILIKE ? THEN 0 ELSE 1 END", c.code, ^prefix),
          asc: fragment("length(?)", c.code),
          asc: c.code
        ],
        limit: ^limit

    query =
      if type_filter && type_filter in ~w(diagnosis procedure chemical) do
        from c in base, where: c.type == ^type_filter
      else
        base
      end

    Repo.all(query)
  end

  defp format_result(entry) do
    %{
      code: entry.code,
      description: entry.description,
      type: entry.type,
      metadata: entry.metadata
    }
  end

  defp parse_limit(nil), do: @default_results
  defp parse_limit(s) when is_binary(s) do
    case Integer.parse(s) do
      {n, ""} -> min(max(n, 1), @max_results)
      _ -> @default_results
    end
  end

  defp sanitize(s), do: String.replace(s, ~r/[%_]/, "\\\\\\0")
end
