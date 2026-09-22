defmodule AppWeb.Cie10ControllerTest do
  use AppWeb.ConnCase, async: true

  alias App.Repo
  alias App.Cie10Code

  setup do
    Repo.insert!(%Cie10Code{
      code: "A00",
      description: "Cólera",
      type: "diagnosis",
      metadata: %{perinatal: false, pediatric: false, maternity: false, adult: false}
    })

    Repo.insert!(%Cie10Code{
      code: "A00.0",
      description: "Cólera debido a Vibrio cholerae 01",
      type: "diagnosis",
      metadata: %{}
    })

    Repo.insert!(%Cie10Code{
      code: "0016070",
      description: "Derivación de ventrículo cerebral",
      type: "procedure",
      metadata: %{class_name: "Médico-Quirúrgica", approach: "Abierto"}
    })

    Repo.insert!(%Cie10Code{
      code: "T51.3X1",
      description: "1-Propanol",
      type: "chemical",
      metadata: %{all_codes: ["T51.3X1", "T51.3X2", "T51.3X3", "T51.3X4"]}
    })

    :ok
  end

  # ── GET /api/cie10/search ─────────────────────────────────────────────────

  describe "search/2" do
    test "returns results matching code prefix", %{conn: conn} do
      conn = get(conn, "/api/cie10/search?q=A00")
      %{"results" => results} = json_response(conn, 200)

      assert results != []
      codes = Enum.map(results, & &1["code"])
      assert "A00" in codes
    end

    test "returns results matching description substring", %{conn: conn} do
      conn = get(conn, "/api/cie10/search?q=cólera")
      %{"results" => results} = json_response(conn, 200)

      assert results != []
      descriptions = Enum.map(results, & &1["description"])
      assert Enum.any?(descriptions, &String.contains?(String.downcase(&1), "cólera"))
    end

    test "returns empty for query shorter than 2 chars", %{conn: conn} do
      conn = get(conn, "/api/cie10/search?q=A")
      %{"results" => results} = json_response(conn, 200)
      assert results == []
    end

    test "returns empty when no q param", %{conn: conn} do
      conn = get(conn, "/api/cie10/search")
      %{"results" => results} = json_response(conn, 200)
      assert results == []
    end

    test "filters by type=diagnosis", %{conn: conn} do
      conn = get(conn, "/api/cie10/search?q=A&type=diagnosis")
      %{"results" => results} = json_response(conn, 200)

      assert Enum.all?(results, &(&1["type"] == "diagnosis"))
    end

    test "filters by type=procedure", %{conn: conn} do
      conn = get(conn, "/api/cie10/search?q=0016&type=procedure")
      %{"results" => results} = json_response(conn, 200)

      assert Enum.all?(results, &(&1["type"] == "procedure"))
    end

    test "filters by type=chemical", %{conn: conn} do
      conn = get(conn, "/api/cie10/search?q=T51&type=chemical")
      %{"results" => results} = json_response(conn, 200)

      assert Enum.all?(results, &(&1["type"] == "chemical"))
    end

    test "respects limit parameter", %{conn: conn} do
      conn = get(conn, "/api/cie10/search?q=A&limit=1")
      %{"results" => results} = json_response(conn, 200)

      assert length(results) <= 1
    end

    test "caps limit at 20", %{conn: conn} do
      conn = get(conn, "/api/cie10/search?q=A&limit=999")
      %{"results" => results} = json_response(conn, 200)

      assert length(results) <= 20
    end

    test "result includes code, description, type and metadata", %{conn: conn} do
      conn = get(conn, "/api/cie10/search?q=A00")
      %{"results" => [first | _]} = json_response(conn, 200)

      assert Map.has_key?(first, "code")
      assert Map.has_key?(first, "description")
      assert Map.has_key?(first, "type")
      assert Map.has_key?(first, "metadata")
    end

    test "code prefix matches are ranked before description matches", %{conn: conn} do
      conn = get(conn, "/api/cie10/search?q=A00")
      %{"results" => results} = json_response(conn, 200)

      first = hd(results)
      assert String.starts_with?(first["code"], "A00")
    end

    test "ignores unknown type filter", %{conn: conn} do
      conn = get(conn, "/api/cie10/search?q=A00&type=unknown")
      %{"results" => results} = json_response(conn, 200)

      assert is_list(results)
    end
  end

  # ── GET /api/cie10/codes/:code ────────────────────────────────────────────

  describe "show/2" do
    test "returns code details for existing code", %{conn: conn} do
      conn = get(conn, "/api/cie10/codes/A00")
      %{"result" => result} = json_response(conn, 200)

      assert result["code"] == "A00"
      assert result["description"] == "Cólera"
      assert result["type"] == "diagnosis"
    end

    test "returns 404 for unknown code", %{conn: conn} do
      conn = get(conn, "/api/cie10/codes/ZZZZ99")
      assert json_response(conn, 404)["error"] == "Code not found"
    end

    test "lookup is case-insensitive (upcases the code)", %{conn: conn} do
      conn = get(conn, "/api/cie10/codes/a00")
      %{"result" => result} = json_response(conn, 200)

      assert result["code"] == "A00"
    end

    test "returns procedure with metadata", %{conn: conn} do
      conn = get(conn, "/api/cie10/codes/0016070")
      %{"result" => result} = json_response(conn, 200)

      assert result["type"] == "procedure"
      assert result["metadata"]["class_name"] == "Médico-Quirúrgica"
    end

    test "returns chemical with all_codes in metadata", %{conn: conn} do
      conn = get(conn, "/api/cie10/codes/T51.3X1")
      %{"result" => result} = json_response(conn, 200)

      assert result["type"] == "chemical"
      assert "T51.3X1" in result["metadata"]["all_codes"]
    end
  end

  # ── GET /api/cie10/codes/:code/children ───────────────────────────────────

  describe "children/2" do
    test "returns children of a parent code", %{conn: conn} do
      conn = get(conn, "/api/cie10/codes/A00/children")
      %{"children" => children, "is_leaf" => is_leaf} = json_response(conn, 200)

      assert is_list(children)
      assert is_leaf == false
      codes = Enum.map(children, & &1["code"])
      assert "A00.0" in codes
    end

    test "returns is_leaf=true when code has no children", %{conn: conn} do
      conn = get(conn, "/api/cie10/codes/A00.0/children")
      %{"children" => children, "is_leaf" => is_leaf} = json_response(conn, 200)

      assert children == []
      assert is_leaf == true
    end

    test "returns is_leaf=true for completely unknown code", %{conn: conn} do
      conn = get(conn, "/api/cie10/codes/ZZZZ99/children")
      %{"children" => children, "is_leaf" => is_leaf} = json_response(conn, 200)

      assert children == []
      assert is_leaf == true
    end

    test "lookup is case-insensitive", %{conn: conn} do
      conn = get(conn, "/api/cie10/codes/a00/children")
      %{"children" => children} = json_response(conn, 200)

      codes = Enum.map(children, & &1["code"])
      assert "A00.0" in codes
    end

    test "children include is_virtual flag", %{conn: conn} do
      conn = get(conn, "/api/cie10/codes/A00/children")
      %{"children" => children} = json_response(conn, 200)

      assert Enum.all?(children, &Map.has_key?(&1, "is_virtual"))
    end

    test "existing child code has is_virtual=false", %{conn: conn} do
      conn = get(conn, "/api/cie10/codes/A00/children")
      %{"children" => children} = json_response(conn, 200)

      a000 = Enum.find(children, &(&1["code"] == "A00.0"))
      assert a000 != nil
      assert a000["is_virtual"] == false
    end
  end

  # ── Cie10Code.changeset/2 ─────────────────────────────────────────────────

  describe "Cie10Code.changeset/2" do
    test "rejects invalid type" do
      cs = Cie10Code.changeset(%Cie10Code{}, %{code: "Z99", description: "Test", type: "invalid"})
      refute cs.valid?
      assert cs.errors[:type] != nil
    end

    test "rejects missing required fields" do
      cs = Cie10Code.changeset(%Cie10Code{}, %{})
      refute cs.valid?
      assert cs.errors[:code] != nil
      assert cs.errors[:description] != nil
      assert cs.errors[:type] != nil
    end
  end

  describe "search/2: parámetros y filtros" do
    test "una consulta de menos de dos caracteres no busca", %{conn: conn} do
      assert json_response(get(conn, ~p"/api/cie10/search?q=A"), 200)["results"] == []
    end

    test "sin parámetro de búsqueda devuelve lista vacía", %{conn: conn} do
      assert json_response(get(conn, ~p"/api/cie10/search"), 200)["results"] == []
    end

    test "filtra por tipo de código", %{conn: conn} do
      resultados =
        json_response(get(conn, ~p"/api/cie10/search?q=Propanol&type=chemical"), 200)["results"]

      assert Enum.all?(resultados, &(&1["type"] == "chemical"))
    end

    test "un límite no numérico cae al valor por defecto en vez de fallar", %{conn: conn} do
      assert json_response(get(conn, ~p"/api/cie10/search?q=Cólera&limit=muchos"), 200)["results"]
    end

    test "respeta el límite indicado", %{conn: conn} do
      resultados = json_response(get(conn, ~p"/api/cie10/search?q=e&limit=1"), 200)["results"]
      assert length(resultados) <= 1
    end

    test "los comodines de SQL en la consulta se tratan como texto", %{conn: conn} do
      # Sin escapar, un '%' haría que la búsqueda devolviera el catálogo entero.
      resultados = json_response(get(conn, ~p"/api/cie10/search?q=%25"), 200)["results"]
      assert resultados == []
    end
  end

  describe "children/2: casos límite" do
    test "un código sin hijos se marca como hoja", %{conn: conn} do
      %App.Cie10Code{code: "Z99.9", type: "diagnosis", description: "Sin hijos", metadata: %{}}
      |> App.Repo.insert!()

      respuesta = json_response(get(conn, ~p"/api/cie10/codes/Z99.9/children"), 200)
      assert respuesta["is_leaf"] == true
      assert respuesta["children"] == []
    end

    test "un código inexistente también se considera hoja", %{conn: conn} do
      respuesta = json_response(get(conn, ~p"/api/cie10/codes/XYZ99/children"), 200)
      assert respuesta["is_leaf"] == true
    end
  end
end
