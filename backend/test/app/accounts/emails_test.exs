defmodule App.Accounts.EmailsTest do
  use ExUnit.Case, async: false
  import Swoosh.TestAssertions

  alias App.Accounts.Emails
  alias App.Accounts.User

  defp user_fixture(overrides \\ %{}) do
    struct(
      %User{
        id: Ecto.UUID.generate(),
        first_name: "Ana",
        last_name: "García",
        email: "ana@example.com",
        confirmation_token: "testtoken123",
        locale: "es"
      },
      overrides
    )
  end

  describe "send_confirmation/1" do
    test "sends to the user's email address" do
      user = user_fixture()
      Emails.send_confirmation(user)

      assert_email_sent(fn email ->
        assert email.to == [{"Ana García", "ana@example.com"}]
      end)
    end

    test "subject is translated, not a raw key" do
      user = user_fixture()
      Emails.send_confirmation(user)

      assert_email_sent(fn email ->
        refute email.subject =~ "email.confirmations"
        assert email.subject =~ "Clicoder"
      end)
    end

    test "HTML body contains user's name (interpolation)" do
      user = user_fixture()
      Emails.send_confirmation(user)

      assert_email_sent(fn email ->
        assert email.html_body =~ "Ana"
        assert email.html_body =~ "García"
        refute email.html_body =~ "{first_name}"
        refute email.html_body =~ "{last_name}"
      end)
    end

    test "HTML body contains the confirmation URL with token" do
      user = user_fixture(%{confirmation_token: "tok_abc42"})
      Emails.send_confirmation(user)

      assert_email_sent(fn email ->
        assert email.html_body =~ "tok_abc42"
        assert email.html_body =~ "confirm-email"
      end)
    end

    test "plain text body contains the confirmation URL" do
      user = user_fixture(%{confirmation_token: "tok_abc42"})
      Emails.send_confirmation(user)

      assert_email_sent(fn email ->
        assert email.text_body =~ "tok_abc42"
        assert email.text_body =~ "confirm-email"
      end)
    end

    test "no raw translation keys appear in the email body" do
      user = user_fixture()
      Emails.send_confirmation(user)

      assert_email_sent(fn email ->
        refute email.html_body =~ "email.confirmations"
        refute email.text_body =~ "email.confirmations"
        refute email.html_body =~ "app.title"
        refute email.text_body =~ "app.title"
      end)
    end

    test "sends email in English for en locale" do
      user = user_fixture(%{locale: "en"})
      Emails.send_confirmation(user)

      assert_email_sent(fn email ->
        refute email.subject =~ "email.confirmations"
        assert email.subject =~ "Clicoder"
        assert email.html_body =~ "Ana"
        assert email.html_body =~ "Welcome"
        refute email.html_body =~ "email.confirmations"
      end)
    end
  end
end
