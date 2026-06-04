defmodule App.TranslationsTest do
  use ExUnit.Case, async: true

  alias App.Translations

  describe "t/3 - key lookup" do
    test "resolves a 2-level key in Spanish" do
      assert Translations.t("es", "auth.login") == "Iniciar sesión"
    end

    test "resolves a 2-level key in English" do
      assert Translations.t("en", "auth.login") == "Sign in"
    end

    test "resolves a 3-level key in Spanish" do
      assert Translations.t("es", "email.confirmations.cta") == "Confirmar cuenta"
    end

    test "resolves a 3-level key in English" do
      assert Translations.t("en", "email.confirmations.cta") == "Confirm account"
    end

    test "returns the key itself when not found" do
      assert Translations.t("es", "nonexistent.key.here") == "nonexistent.key.here"
    end

    test "falls back to default locale for unsupported locale" do
      assert Translations.t("xx", "auth.login") == Translations.t("es", "auth.login")
    end
  end

  describe "t/3 - interpolation" do
    test "interpolates name variables in greeting" do
      result =
        Translations.t("es", "email.confirmations.greeting",
          first_name: "Ana",
          last_name: "García"
        )

      assert result == "Bienvenido/a, Ana García"
    end

    test "interpolates app_title in intro" do
      result = Translations.t("es", "email.confirmations.intro", app_title: "Mi App")
      assert result == "Gracias por registrarte en el Mi App."
    end

    test "leaves unreplaced placeholders when var is missing" do
      result = Translations.t("es", "email.confirmations.greeting", first_name: "Ana")
      assert result =~ "{last_name}"
      assert result =~ "Ana"
    end

    test "no interpolation with empty vars" do
      raw = Translations.t("es", "email.confirmations.greeting", [])
      assert raw =~ "{first_name}"
    end
  end
end
