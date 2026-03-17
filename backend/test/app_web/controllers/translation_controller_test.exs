defmodule AppWeb.TranslationControllerTest do
  use AppWeb.ConnCase, async: true

  # ---------------------------------------------------------------------------
  # GET /api/translations/:locale
  # ---------------------------------------------------------------------------

  describe "show/2" do
    test "returns Spanish translations for locale 'es'", %{conn: conn} do
      conn = get(conn, "/api/translations/es")
      body = json_response(conn, 200)

      # Top-level keys present in es.yml
      assert Map.has_key?(body, "auth")
      assert Map.has_key?(body, "app")
      assert Map.has_key?(body, "sidebar")
      assert Map.has_key?(body, "chat")
      assert Map.has_key?(body, "errors")
      assert Map.has_key?(body, "cards")
    end

    test "returns English translations for locale 'en'", %{conn: conn} do
      conn = get(conn, "/api/translations/en")
      body = json_response(conn, 200)

      assert Map.has_key?(body, "auth")
      assert Map.has_key?(body, "app")
      assert Map.has_key?(body, "sidebar")
    end

    test "Spanish auth section contains expected keys", %{conn: conn} do
      conn = get(conn, "/api/translations/es")
      %{"auth" => auth} = json_response(conn, 200)

      assert Map.has_key?(auth, "login")
      assert Map.has_key?(auth, "register")
      assert Map.has_key?(auth, "error_invalid_credentials")
      assert Map.has_key?(auth, "error_not_confirmed")
    end

    test "English auth section contains expected keys", %{conn: conn} do
      conn = get(conn, "/api/translations/en")
      %{"auth" => auth} = json_response(conn, 200)

      assert Map.has_key?(auth, "login")
      assert Map.has_key?(auth, "register")
      assert Map.has_key?(auth, "error_invalid_credentials")
    end

    test "Spanish and English translations differ for the same key", %{conn: conn} do
      conn_es = get(conn, "/api/translations/es")
      conn_en = get(Phoenix.ConnTest.build_conn(), "/api/translations/en")

      %{"auth" => auth_es} = json_response(conn_es, 200)
      %{"auth" => auth_en} = json_response(conn_en, 200)

      refute auth_es["login"] == auth_en["login"]
    end

    test "unknown locale falls back to Spanish (default)", %{conn: conn} do
      conn = get(conn, "/api/translations/fr")
      body = json_response(conn, 200)

      # Falls back to 'es' — verify the Spanish content is served
      assert Map.has_key?(body, "auth")

      conn_es = get(Phoenix.ConnTest.build_conn(), "/api/translations/es")
      es_body = json_response(conn_es, 200)

      assert body == es_body
    end

    test "locale 'zz' (unsupported) also falls back to Spanish", %{conn: conn} do
      conn = get(conn, "/api/translations/zz")
      body = json_response(conn, 200)

      assert Map.has_key?(body, "auth")
    end

    test "translation values are strings, not nested structures for leaf keys", %{conn: conn} do
      conn = get(conn, "/api/translations/en")
      %{"auth" => auth} = json_response(conn, 200)

      assert is_binary(auth["login"])
      assert is_binary(auth["register"])
    end
  end
end
