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

      assert length(results) >= 1
      codes = Enum.map(results, & &1["code"])
      assert "A00" in codes
    end

    test "returns results matching description substring", %{conn: conn} do
      conn = get(conn, "/api/cie10/search?q=cólera")
      %{"results" => results} = json_response(conn, 200)

      assert length(results) >= 1
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
end
