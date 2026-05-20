defmodule AppWeb.Router do
  use AppWeb, :router

  pipeline :api do
    plug :accepts, ["json"]
    plug AppWeb.Plugs.SetLocale
  end

  pipeline :require_auth do
    plug AppWeb.Plugs.RequireAuth
  end

  scope "/api", AppWeb do
    pipe_through :api

    post "/auth/register", AuthController, :register
    post "/auth/login", AuthController, :login
    get "/auth/confirm/:token", AuthController, :confirm

    get "/translations/:locale", TranslationController, :show

    # CIE-10 reference (public — read-only catalogue)
    get "/cie10/search", Cie10Controller, :search
    get "/cie10/codes/:code/children", Cie10Controller, :children
    get "/cie10/codes/:code", Cie10Controller, :show

    # Authenticated routes
    pipe_through [:require_auth]
    get "/conversations", ConversationController, :index
    get "/conversations/trash", ConversationController, :trash
    delete "/conversations/:conversation_id", ConversationController, :delete
    put "/conversations/:conversation_id/restore", ConversationController, :restore
    put "/users/locale", AuthController, :update_locale
  end

  # Admin backoffice
  scope "/admin", AppWeb.Admin, as: :admin do
    pipe_through [:fetch_session, :protect_from_forgery]

    get "/login", SessionController, :new
    post "/login", SessionController, :create
    delete "/logout", SessionController, :delete
  end

  scope "/admin", AppWeb.Admin, as: :admin do
    pipe_through [:fetch_session, :protect_from_forgery, AppWeb.Plugs.RequireAdmin]

    live_session :admin,
      on_mount: [],
      layout: {AppWeb.Admin.AdminLayout, :admin} do
      live "/users", UserLive.Index, :index
      live "/users/:id", UserLive.Show, :show
    end
  end

  # Enable LiveDashboard and Swoosh mailbox preview in development
  if Application.compile_env(:app, :dev_routes) do
    # If you want to use the LiveDashboard in production, you should put
    # it behind authentication and allow only admins to access it.
    # If your application does not have an admins-only section yet,
    # you can use Plug.BasicAuth to set up some basic authentication
    # as long as you are also using SSL (which you should anyway).
    import Phoenix.LiveDashboard.Router

    scope "/dev" do
      pipe_through [:fetch_session, :protect_from_forgery]

      live_dashboard "/dashboard", metrics: AppWeb.Telemetry
      forward "/mailbox", Plug.Swoosh.MailboxPreview
    end
  end
end
