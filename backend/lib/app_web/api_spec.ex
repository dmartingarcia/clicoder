defmodule AppWeb.ApiSpec do
  @behaviour OpenApiSpex.OpenApi

  alias OpenApiSpex.{Components, Info, OpenApi, SecurityScheme, Server}

  @impl OpenApiSpex.OpenApi
  def spec do
    %OpenApi{
      info: %Info{
        title: "CIE-10 API",
        description: "API REST de la plataforma de codificación CIE-10.",
        version: "1.0.0"
      },
      servers: [%Server{url: "/"}],
      components: %Components{
        securitySchemes: %{
          "bearer_auth" => %SecurityScheme{type: "http", scheme: "bearer"}
        }
      },
      paths: OpenApiSpex.Paths.from_router(AppWeb.Router)
    }
    |> OpenApiSpex.resolve_schema_modules()
  end
end
