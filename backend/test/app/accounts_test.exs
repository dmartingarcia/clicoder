defmodule App.AccountsTest do
  use App.DataCase, async: true

  alias App.Accounts
  alias App.Fixtures

  describe "register_user/1" do
    test "creates a confirmed-pending user with valid attrs" do
      attrs = %{
        "first_name" => "Ana",
        "last_name" => "García",
        "username" => "anagarcia",
        "email" => "ana@example.com",
        "password" => "secretpass123"
      }

      assert {:ok, user} = Accounts.register_user(attrs)
      assert user.email == "ana@example.com"
      assert user.username == "anagarcia"
      assert user.password_hash != nil
      assert user.confirmation_token != nil
      assert user.confirmed_at == nil
    end

    test "hashes the password" do
      attrs = %{
        "first_name" => "A",
        "last_name" => "B",
        "username" => "abuser",
        "email" => "ab@example.com",
        "password" => "plaintextpass123"
      }

      {:ok, user} = Accounts.register_user(attrs)
      refute user.password_hash == "plaintextpass123"
    end

    test "returns error on duplicate email" do
      existing = Fixtures.user_fixture()

      attrs = %{
        "first_name" => "Other",
        "last_name" => "User",
        "username" => "otherusername",
        "email" => existing.email,
        "password" => "password12345"
      }

      assert {:error, changeset} = Accounts.register_user(attrs)
      assert %{email: ["email ya registrado"]} = errors_on(changeset)
    end

    test "returns error on duplicate username" do
      existing = Fixtures.user_fixture()

      attrs = %{
        "first_name" => "Other",
        "last_name" => "User",
        "username" => existing.username,
        "email" => "unique@example.com",
        "password" => "password12345"
      }

      assert {:error, changeset} = Accounts.register_user(attrs)
      assert %{username: ["nombre de usuario no disponible"]} = errors_on(changeset)
    end

    test "returns error with invalid email format" do
      attrs = %{
        "first_name" => "A",
        "last_name" => "B",
        "username" => "validuser",
        "email" => "notanemail",
        "password" => "password12345"
      }

      assert {:error, changeset} = Accounts.register_user(attrs)
      assert %{email: _} = errors_on(changeset)
    end

    test "returns error with password too short" do
      attrs = %{
        "first_name" => "A",
        "last_name" => "B",
        "username" => "validuser2",
        "email" => "valid2@example.com",
        "password" => "12345"
      }

      assert {:error, changeset} = Accounts.register_user(attrs)
      assert %{password: _} = errors_on(changeset)
    end

    test "returns error with username containing special chars" do
      attrs = %{
        "first_name" => "A",
        "last_name" => "B",
        "username" => "bad user!",
        "email" => "valid3@example.com",
        "password" => "password12345"
      }

      assert {:error, changeset} = Accounts.register_user(attrs)
      assert %{username: _} = errors_on(changeset)
    end
  end

  describe "confirm_user/1" do
    test "confirms a user with a valid token" do
      user = Fixtures.unconfirmed_user_fixture()
      assert user.confirmed_at == nil
      assert user.confirmation_token != nil

      assert {:ok, confirmed} = Accounts.confirm_user(user.confirmation_token)
      assert confirmed.confirmed_at != nil
      assert confirmed.confirmation_token == nil
    end

    test "returns error for invalid token" do
      assert {:error, :invalid_token} = Accounts.confirm_user("invalid-token")
    end

    test "returns error for already-used token" do
      user = Fixtures.unconfirmed_user_fixture()
      {:ok, _} = Accounts.confirm_user(user.confirmation_token)
      assert {:error, :invalid_token} = Accounts.confirm_user(user.confirmation_token)
    end
  end

  describe "authenticate/2" do
    test "returns user with valid credentials" do
      user = Fixtures.user_fixture(%{"password" => "mypassword1234"})
      assert {:ok, authenticated} = Accounts.authenticate(user.email, "mypassword1234")
      assert authenticated.id == user.id
    end

    test "returns error for wrong password" do
      user = Fixtures.user_fixture()
      assert {:error, :invalid_credentials} = Accounts.authenticate(user.email, "wrongpassword")
    end

    test "returns error for unconfirmed user" do
      user = Fixtures.unconfirmed_user_fixture()
      assert {:error, :email_not_confirmed} = Accounts.authenticate(user.email, "password12345")
    end

    test "returns error for nonexistent email" do
      assert {:error, :invalid_credentials} =
               Accounts.authenticate("nobody@example.com", "password")
    end
  end

  describe "get_user_by_email/1" do
    test "returns user when exists" do
      user = Fixtures.user_fixture()
      assert found = Accounts.get_user_by_email(user.email)
      assert found.id == user.id
    end

    test "returns nil when not found" do
      assert Accounts.get_user_by_email("missing@example.com") == nil
    end
  end

  describe "get_user/1" do
    test "returns user by id" do
      user = Fixtures.user_fixture()
      assert found = Accounts.get_user(user.id)
      assert found.id == user.id
    end

    test "returns nil for unknown id" do
      assert Accounts.get_user(Ecto.UUID.generate()) == nil
    end
  end

  describe "update_locale/2" do
    test "updates locale for existing user" do
      user = Fixtures.user_fixture(%{"locale" => "es"})
      assert {:ok, updated} = Accounts.update_locale(user.id, "en")
      assert updated.locale == "en"
    end

    test "returns error for unknown user" do
      assert {:error, :not_found} = Accounts.update_locale(Ecto.UUID.generate(), "en")
    end
  end
end
