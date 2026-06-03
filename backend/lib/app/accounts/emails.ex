defmodule App.Accounts.Emails do
  import Swoosh.Email

  alias App.Mailer
  alias App.Translations

  def send_confirmation(user) do
    locale = user.locale || "es"
    domain = System.get_env("DOMAIN") || "localhost"

    base_url =
      if domain == "localhost", do: "http://localhost:4000", else: "https://api.#{domain}"

    confirm_url = "#{base_url}/api/auth/confirm/#{user.confirmation_token}"
    app_title = Translations.t(locale, "app.title")
    subject_line = Translations.t(locale, "email.confirmations.registration_subject")

    email =
      new()
      |> to({user.first_name <> " " <> user.last_name, user.email})
      |> from(from_email())
      |> subject(subject_line)
      |> html_body("""
      <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #1d4ed8;">Bienvenido/a, Dr. #{user.first_name} #{user.last_name}</h2>
        <p>Gracias por registrarte en el <strong>Clasificador CIE-10</strong>.</p>
        <p>Para activar tu cuenta, haz clic en el siguiente enlace:</p>
        <a href="#{confirm_url}"
           style="display:inline-block; background:#1d4ed8; color:white; padding:12px 24px;
                  border-radius:8px; text-decoration:none; font-weight:600; margin:16px 0;">
          Confirmar cuenta
        </a>
        <p style="color:#6b7280; font-size:13px;">
          Si no puedes hacer clic, copia y pega esta URL en tu navegador:<br>
          <code>#{confirm_url}</code>
        </p>
        <hr style="border:none; border-top:1px solid #e5e7eb; margin-top:24px;">
        <p style="color:#9ca3af; font-size:12px;">
          Si no creaste esta cuenta, puedes ignorar este mensaje.
        </p>
      </div>
      """)
      |> text_body("""
      Bienvenido/a, Dr. #{user.first_name} #{user.last_name}

      Confirma tu cuenta visitando:
      #{confirm_url}

      Si no creaste esta cuenta, ignora este mensaje.
      """)

    Mailer.deliver(email)
  end

  defp from_email do
    domain = System.get_env("DOMAIN") || "localhost"
    app_title = Translations.t("es", "app.title")
    {app_title, "noreply@#{domain}"}
  end
end
