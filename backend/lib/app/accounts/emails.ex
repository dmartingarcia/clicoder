defmodule App.Accounts.Emails do
  import Swoosh.Email

  alias App.Mailer
  alias App.Translations

  def send_confirmation(user) do
    locale = user_locale(user)
    vars = [first_name: user.first_name, last_name: user.last_name, app_title: app_title(locale)]

    confirm_url = "#{fe_base_url()}/confirm-email?token=#{user.confirmation_token}"

    greeting = Translations.t(locale, "email.confirmations.greeting", vars)
    intro = Translations.t(locale, "email.confirmations.intro", vars)
    instruction = Translations.t(locale, "email.confirmations.instruction")
    cta = Translations.t(locale, "email.confirmations.cta")
    fallback = Translations.t(locale, "email.confirmations.fallback_hint")
    ignore = Translations.t(locale, "email.confirmations.ignore")
    plain_confirm = Translations.t(locale, "email.confirmations.plain_confirm")
    subject_line = Translations.t(locale, "email.confirmations.registration_subject")

    email =
      new()
      |> to({user.first_name <> " " <> user.last_name, user.email})
      |> from(from_email(locale))
      |> subject(subject_line)
      |> html_body("""
      <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #1d4ed8;">#{greeting}</h2>
        <p>#{intro}</p>
        <p>#{instruction}</p>
        <a href="#{confirm_url}"
           style="display:inline-block; background:#1d4ed8; color:white; padding:12px 24px;
                  border-radius:8px; text-decoration:none; font-weight:600; margin:16px 0;">
          #{cta}
        </a>
        <p style="color:#6b7280; font-size:13px;">
          #{fallback}<br>
          <code>#{confirm_url}</code>
        </p>
        <hr style="border:none; border-top:1px solid #e5e7eb; margin-top:24px;">
        <p style="color:#9ca3af; font-size:12px;">
          #{ignore}
        </p>
      </div>
      """)
      |> text_body("""
      #{greeting}

      #{plain_confirm}
      #{confirm_url}

      #{ignore}
      """)

    Mailer.deliver(email)
  end

  defp domain do
    System.get_env("DOMAIN") || "localhost"
  end

  defp fe_base_url do
    if domain() == "localhost" do
      "http://localhost:3000"
    else
      "https://#{domain()}"
    end
  end

  defp user_locale(user) do
    user.locale || "es"
  end

  defp app_title(locale) do
    Translations.t(locale, "app.title")
  end

  defp from_email(locale) do
    {app_title(locale), "noreply@#{domain()}"}
  end
end
