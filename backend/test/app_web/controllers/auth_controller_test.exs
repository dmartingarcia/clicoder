defmodule AppWeb.AuthControllerTest do
  use AppWeb.ConnCase, async: true

  import App.Fixtures

  # ---------------------------------------------------------------------------
  # POST /api/auth/register
  # ---------------------------------------------------------------------------

  describe "register/2" do
    test "returns 201 and pending_confirmation status on success", %{conn: conn} do
      unique = System.unique_integer([:positive])

      params = %{
        "first_name" => "Ana",
        "last_name" => "García",
        "username" => "anagarcia#{unique}",
        "email" => "ana#{unique}@example.com",
        "password" => "secret123"
      }

      conn = post(conn, "/api/auth/register", params)

      assert %{"status" => "pending_confirmation", "user" => user_map} = json_response(conn, 201)
      assert user_map["email"] == params["email"]
    end

    test "returns 422 when email is already registered", %{conn: conn} do
      existing = user_fixture()

      unique = System.unique_integer([:positive])

      params = %{
        "first_name" => "Other",
        "last_name" => "Person",
        "username" => "otherperson#{unique}",
        "email" => existing.email,
        "password" => "password123"
      }

      conn = post(conn, "/api/auth/register", params)

      assert %{"errors" => errors} = json_response(conn, 422)
      assert Map.has_key?(errors, "email")
    end

    test "returns 422 when password is too short", %{conn: conn} do
      unique = System.unique_integer([:positive])

      params = %{
        "first_name" => "Short",
        "last_name" => "Pass",
        "username" => "shortpass#{unique}",
        "email" => "short#{unique}@example.com",
        "password" => "abc"
      }

      conn = post(conn, "/api/auth/register", params)

      assert %{"errors" => errors} = json_response(conn, 422)
      assert Map.has_key?(errors, "password")
    end

    test "returns 422 when required fields are missing", %{conn: conn} do
      conn = post(conn, "/api/auth/register", %{})

      assert %{"errors" => errors} = json_response(conn, 422)
      # All required fields should appear as errors
      assert Map.has_key?(errors, "first_name") or Map.has_key?(errors, "email")
    end

    test "returns 422 when username has invalid characters", %{conn: conn} do
      unique = System.unique_integer([:positive])

      params = %{
        "first_name" => "Bad",
        "last_name" => "Username",
        "username" => "bad user name!",
        "email" => "bad#{unique}@example.com",
        "password" => "password123"
      }

      conn = post(conn, "/api/auth/register", params)

      assert %{"errors" => errors} = json_response(conn, 422)
      assert Map.has_key?(errors, "username")
    end

    test "returns 422 when username is too short", %{conn: conn} do
      unique = System.unique_integer([:positive])

      params = %{
        "first_name" => "Sh",
        "last_name" => "Rt",
        "username" => "ab",
        "email" => "ab#{unique}@example.com",
        "password" => "password123"
      }

      conn = post(conn, "/api/auth/register", params)

      assert %{"errors" => errors} = json_response(conn, 422)
      assert Map.has_key?(errors, "username")
    end
  end

  # ---------------------------------------------------------------------------
  # POST /api/auth/login
  # ---------------------------------------------------------------------------

  describe "login/2" do
    test "returns 200 with token and user info on success", %{conn: conn} do
      user = user_fixture(%{"email" => "login_ok@example.com", "password" => "mypassword"})

      conn = post(conn, "/api/auth/login", %{"email" => user.email, "password" => "mypassword"})

      assert %{"token" => token, "user" => user_data} = json_response(conn, 200)

      assert is_binary(token)
      assert token != ""

      assert user_data["email"] == user.email
      assert user_data["first_name"] == user.first_name
      assert user_data["last_name"] == user.last_name
      assert user_data["username"] == user.username
      assert is_binary(user_data["id"])
    end

    test "returned token is a valid Phoenix.Token for the user", %{conn: conn} do
      user = user_fixture(%{"email" => "token_valid@example.com", "password" => "mypassword"})

      conn = post(conn, "/api/auth/login", %{"email" => user.email, "password" => "mypassword"})

      %{"token" => token} = json_response(conn, 200)

      assert {:ok, user_id} =
               Phoenix.Token.verify(AppWeb.Endpoint, "user auth", token, max_age: 86_400 * 30)

      assert to_string(user_id) == to_string(user.id)
    end

    test "returns 401 when password is wrong", %{conn: conn} do
      user = user_fixture(%{"email" => "wrong_pass@example.com", "password" => "correctpass"})

      conn = post(conn, "/api/auth/login", %{"email" => user.email, "password" => "wrongpass"})

      assert %{"error" => _msg} = json_response(conn, 401)
    end

    test "returns 401 when email does not exist", %{conn: conn} do
      conn =
        post(conn, "/api/auth/login", %{
          "email" => "nobody@example.com",
          "password" => "anything"
        })

      assert %{"error" => _msg} = json_response(conn, 401)
    end

    test "returns 403 when user email is not confirmed", %{conn: conn} do
      user = unconfirmed_user_fixture(%{"email" => "unconfirmed@example.com"})

      conn =
        post(conn, "/api/auth/login", %{
          "email" => user.email,
          "password" => "password123"
        })

      assert %{"error" => _msg} = json_response(conn, 403)
    end
  end

  # ---------------------------------------------------------------------------
  # GET /api/auth/confirm/:token
  # ---------------------------------------------------------------------------

  describe "confirm/2" do
    test "valid token confirms the user and redirects", %{conn: conn} do
      user = unconfirmed_user_fixture()
      token = user.confirmation_token

      conn = get(conn, "/api/auth/confirm/#{token}")

      # The controller redirects to the frontend with confirmed=1
      assert conn.status == 302
      location = get_resp_header(conn, "location") |> List.first()
      assert String.contains?(location, "confirmed=1")
      assert String.contains?(location, "token=")
    end

    test "invalid token returns 404", %{conn: conn} do
      conn = get(conn, "/api/auth/confirm/invalid-token-that-does-not-exist")

      assert %{"error" => _msg} = json_response(conn, 404)
    end

    test "already-used token returns 404", %{conn: conn} do
      user = unconfirmed_user_fixture()
      token = user.confirmation_token

      # Confirm once — this nils the token in the DB
      App.Accounts.confirm_user(token)

      # Second attempt should fail
      conn = get(conn, "/api/auth/confirm/#{token}")
      assert %{"error" => _msg} = json_response(conn, 404)
    end
  end
end
