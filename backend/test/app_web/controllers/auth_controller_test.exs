defmodule AppWeb.AuthControllerTest do
  use AppWeb.ConnCase, async: true

  import App.Fixtures

  describe "register/2" do
    test "returns 201 and pending_confirmation status on success", %{conn: conn} do
      unique = System.unique_integer([:positive])

      params = %{
        "first_name" => "Ana",
        "last_name" => "García",
        "username" => "anagarcia#{unique}",
        "email" => "ana#{unique}@example.com",
        "password" => "secretpass123"
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
        "password" => "password12345"
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
      assert Map.has_key?(errors, "first_name") or Map.has_key?(errors, "email")
    end

    test "returns 422 when username has invalid characters", %{conn: conn} do
      unique = System.unique_integer([:positive])

      params = %{
        "first_name" => "Bad",
        "last_name" => "Username",
        "username" => "bad user name!",
        "email" => "bad#{unique}@example.com",
        "password" => "password12345"
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
        "password" => "password12345"
      }

      conn = post(conn, "/api/auth/register", params)

      assert %{"errors" => errors} = json_response(conn, 422)
      assert Map.has_key?(errors, "username")
    end
  end

  describe "login/2" do
    test "returns 200 with token and user info on success", %{conn: conn} do
      user = user_fixture(%{"email" => "login_ok@example.com", "password" => "mypassword1234"})

      conn =
        post(conn, "/api/auth/login", %{"email" => user.email, "password" => "mypassword1234"})

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
      user = user_fixture(%{"email" => "token_valid@example.com", "password" => "mypassword1234"})

      conn =
        post(conn, "/api/auth/login", %{"email" => user.email, "password" => "mypassword1234"})

      %{"token" => token} = json_response(conn, 200)

      assert {:ok, user_id} =
               Phoenix.Token.verify(AppWeb.Endpoint, "user auth", token, max_age: 86_400 * 30)

      assert to_string(user_id) == to_string(user.id)
    end

    test "returns 401 when password is wrong", %{conn: conn} do
      user = user_fixture(%{"email" => "wrong_pass@example.com", "password" => "correctpass12"})

      conn = post(conn, "/api/auth/login", %{"email" => user.email, "password" => "wrongpass"})

      assert %{"error" => _msg} = json_response(conn, 401)
    end

    test "returns 401 when email does not exist", %{conn: conn} do
      conn =
        post(conn, "/api/auth/login", %{
          "email" => "nobody@example.com",
          "password" => "anything12345"
        })

      assert %{"error" => _msg} = json_response(conn, 401)
    end

    test "returns 403 when user email is not confirmed", %{conn: conn} do
      user = unconfirmed_user_fixture(%{"email" => "unconfirmed@example.com"})

      conn =
        post(conn, "/api/auth/login", %{
          "email" => user.email,
          "password" => "password12345"
        })

      assert %{"error" => _msg} = json_response(conn, 403)
    end
  end

  describe "confirm/2" do
    test "valid token confirms the user and returns auth token", %{conn: conn} do
      user = unconfirmed_user_fixture()
      token = user.confirmation_token

      conn = get(conn, "/api/auth/confirm/#{token}")

      body = json_response(conn, 200)
      assert Map.has_key?(body, "token")
      assert get_in(body, ["user", "id"]) == user.id
    end

    test "invalid token returns 404", %{conn: conn} do
      conn = get(conn, "/api/auth/confirm/invalid-token-that-does-not-exist")

      assert %{"error" => _msg} = json_response(conn, 404)
    end

    test "already-used token returns 404", %{conn: conn} do
      user = unconfirmed_user_fixture()
      token = user.confirmation_token

      App.Accounts.confirm_user(token)

      conn = get(conn, "/api/auth/confirm/#{token}")
      assert %{"error" => _msg} = json_response(conn, 404)
    end
  end

  describe "update_locale/2" do
    test "updates locale and returns the new locale", %{conn: conn} do
      user = user_fixture()
      {auth_key, auth_value} = auth_header(user)

      conn =
        conn
        |> put_req_header(auth_key, auth_value)
        |> put(~p"/api/users/locale", %{"locale" => "en"})

      assert %{"locale" => "en"} = json_response(conn, 200)
    end

    test "returns 401 when not authenticated", %{conn: conn} do
      conn = put(conn, ~p"/api/users/locale", %{"locale" => "en"})
      assert conn.status == 401
    end
  end

  describe "export/2" do
    test "devuelve los datos del usuario y sus conversaciones", %{conn: conn} do
      user = user_fixture()
      conv = conversation_fixture(user)

      %App.Projections.MessageProjection{
        message_id: UUID.uuid4(),
        conversation_id: conv.id,
        user_id: to_string(user.id),
        content: "Informe de prueba",
        message_type: "user",
        timestamp: DateTime.utc_now() |> DateTime.truncate(:second)
      }
      |> App.Repo.insert!()

      conn =
        conn
        |> then(fn c ->
          {k, v} = auth_header(user)
          put_req_header(c, k, v)
        end)
        |> get(~p"/api/users/export")

      datos = json_response(conn, 200)
      assert datos["user"]["email"] == user.email
      assert length(datos["conversations"]) == 1
      assert hd(hd(datos["conversations"])["messages"])["content"] == "Informe de prueba"
    end

    test "sin conversaciones devuelve la lista vacía", %{conn: conn} do
      user = user_fixture()

      conn =
        conn
        |> then(fn c ->
          {k, v} = auth_header(user)
          put_req_header(c, k, v)
        end)
        |> get(~p"/api/users/export")

      assert json_response(conn, 200)["conversations"] == []
    end

    test "sin autenticación devuelve 401", %{conn: conn} do
      assert conn |> get(~p"/api/users/export") |> Map.fetch!(:status) == 401
    end
  end

  describe "delete_account/2" do
    test "borra al usuario y todo lo que cuelga de él", %{conn: conn} do
      user = user_fixture()
      conv = conversation_fixture(user)

      %App.Projections.MessageProjection{
        message_id: UUID.uuid4(),
        conversation_id: conv.id,
        user_id: to_string(user.id),
        content: "dato personal",
        message_type: "user",
        timestamp: DateTime.utc_now() |> DateTime.truncate(:second)
      }
      |> App.Repo.insert!()

      conn =
        conn
        |> then(fn c ->
          {k, v} = auth_header(user)
          put_req_header(c, k, v)
        end)
        |> delete(~p"/api/users/account")

      assert json_response(conn, 200)["ok"] == true

      # El derecho de supresión no se cumple borrando solo la fila del usuario: los mensajes
      # y las conversaciones contienen datos clínicos y tienen que irse con él.
      refute App.Repo.get(App.Accounts.User, user.id)
      assert App.Repo.aggregate(App.Projections.ConversationProjection, :count) == 0
      assert App.Repo.aggregate(App.Projections.MessageProjection, :count) == 0
    end

    test "no toca los datos de otros usuarios", %{conn: conn} do
      victima = user_fixture()
      otro = user_fixture()
      conversation_fixture(otro)

      conn
      |> then(fn c ->
        {k, v} = auth_header(victima)
        put_req_header(c, k, v)
      end)
      |> delete(~p"/api/users/account")

      assert App.Repo.get(App.Accounts.User, otro.id)
      assert App.Repo.aggregate(App.Projections.ConversationProjection, :count) == 1
    end

    test "sin autenticación devuelve 401", %{conn: conn} do
      assert conn |> delete(~p"/api/users/account") |> Map.fetch!(:status) == 401
    end
  end

  describe "update_locale/2 casos adicionales" do
    test "rechaza un idioma que la interfaz no sabe servir", %{conn: conn} do
      user = user_fixture()

      conn =
        conn
        |> then(fn c ->
          {k, v} = auth_header(user)
          put_req_header(c, k, v)
        end)
        |> put(~p"/api/users/locale", %{"locale" => "klingon"})

      assert json_response(conn, 422)["error"]
      # El idioma anterior se conserva: un valor inválido no deja al usuario peor que antes.
      assert App.Repo.get(App.Accounts.User, user.id).locale == "es"
    end

    test "acepta los cinco idiomas de la interfaz", %{conn: conn} do
      user = user_fixture()

      for locale <- App.Accounts.idiomas_admitidos() do
        respuesta =
          build_conn()
          |> then(fn c ->
            {k, v} = auth_header(user)
            put_req_header(c, k, v)
          end)
          |> put(~p"/api/users/locale", %{"locale" => locale})

        assert json_response(respuesta, 200)["locale"] == locale
      end
    end
  end
end
