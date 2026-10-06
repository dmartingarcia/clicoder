defmodule AppWeb.Router do
  use AppWeb, :router
  import Phoenix.LiveView.Router

  pipeline :api do
    plug :accepts, ["json"]
    plug AppWeb.Plugs.SetLocale
    plug OpenApiSpex.Plug.PutApiSpec, module: AppWeb.ApiSpec
  end

  pipeline :rate_limited do
    plug AppWeb.Plugs.RateLimit
  end

  pipeline :require_auth do
    plug AppWeb.Plugs.RequireAuth
  end

  scope "/api" do
    pipe_through :api
    get "/openapi", OpenApiSpex.Plug.RenderSpec, []
  end

  scope "/" do
    pipe_through :browser
    get "/docs", OpenApiSpex.Plug.SwaggerUI, path: "/api/openapi"
  end

  scope "/api", AppWeb do
    pipe_through :api

    get "/health", HealthController, :check

    scope "/" do
      pipe_through [:rate_limited]
      post "/auth/register", AuthController, :register
      post "/auth/login", AuthController, :login
      get "/auth/confirm/:token", AuthController, :confirm
    end

    get "/translations/:locale", TranslationController, :show

    post "/ai/count-tokens", AiController, :count_tokens

    get "/cie10/search", Cie10Controller, :search
    get "/cie10/codes/:code/children", Cie10Controller, :children
    get "/cie10/codes/:code", Cie10Controller, :show

    pipe_through [:require_auth]
    get "/conversations", ConversationController, :index
    get "/conversations/trash", ConversationController, :trash
    delete "/conversations/:conversation_id", ConversationController, :delete
    delete "/conversations/:conversation_id/purge", ConversationController, :purge
    put "/conversations/:conversation_id/restore", ConversationController, :restore
    put "/users/locale", AuthController, :update_locale
    get "/users/export", AuthController, :export
    delete "/users/account", AuthController, :delete_account
  end

  pipeline :browser do
    plug :accepts, ["html"]
    plug :fetch_session
    plug :fetch_live_flash
    plug :protect_from_forgery
    plug :put_secure_browser_headers
  end

  scope "/admin", AppWeb.Admin, as: :admin do
    pipe_through [:browser]

    get "/login", SessionController, :new
    post "/login", SessionController, :create
    delete "/logout", SessionController, :delete
  end

  scope "/admin", AppWeb.Admin, as: :admin do
    pipe_through [:browser, AppWeb.Plugs.RequireAdmin]

    live_session :admin,
      on_mount: [],
      layout: {AppWeb.Admin.AdminLayout, :admin} do
      live "/users", UserLive.Index, :index
      live "/users/:id", UserLive.Show, :show
      live "/conversations", ConversationLive.Index, :index
      live "/conversations/:id", ConversationLive.Show, :show
      live "/settings", SettingsLive, :index
    end
  end

  if Application.compile_env(:app, :dev_routes) do
    import Phoenix.LiveDashboard.Router

    scope "/dev" do
      pipe_through [:browser]

      live_dashboard "/dashboard", metrics: AppWeb.Telemetry, ecto_repos: [App.Repo]
      forward "/mailbox", Plug.Swoosh.MailboxPreview
    end
  end
end
