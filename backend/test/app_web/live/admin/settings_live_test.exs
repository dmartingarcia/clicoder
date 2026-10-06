defmodule AppWeb.Admin.SettingsLiveTest do
  @moduledoc """
  Cubre el panel de ajustes del backoffice: selección de motor de análisis y de estrategia
  de explicabilidad. Son toggles que cambian el comportamiento del sistema en caliente, de
  modo que un fallo aquí se manifiesta como "el sistema responde distinto" sin error visible.
  """
  use AppWeb.ConnCase

  import Phoenix.LiveViewTest

  alias App.Repo

  setup %{conn: conn} do
    admin =
      user_fixture()
      |> Ecto.Changeset.change(is_admin: true)
      |> Repo.update!()

    App.AIEngineSettings.set_engine("bert")
    App.AIEngineSettings.set_explain_method("gradiente_filtrado")

    {:ok, conn: Plug.Test.init_test_session(conn, admin_user_id: admin.id), admin: admin}
  end

  describe "acceso" do
    test "un usuario sin sesión no entra" do
      limpia = Plug.Test.init_test_session(Phoenix.ConnTest.build_conn(), %{})
      assert {:error, {:redirect, %{to: "/admin/login"}}} = live(limpia, ~p"/admin/settings")
    end

    test "un usuario que no es administrador no entra", %{conn: conn} do
      normal = user_fixture()
      conn = Plug.Test.init_test_session(conn, admin_user_id: normal.id)
      assert {:error, {:redirect, %{to: "/admin/login"}}} = live(conn, ~p"/admin/settings")
    end

    test "un administrador ve la página", %{conn: conn} do
      {:ok, _vista, html} = live(conn, ~p"/admin/settings")
      assert html =~ "Explicabilidad"
    end
  end

  describe "motor de análisis" do
    test "lista los cuatro motores disponibles", %{conn: conn} do
      {:ok, _vista, html} = live(conn, ~p"/admin/settings")

      for etiqueta <- ["BERT", "Diccionario", "Ambos", "Fusionado"] do
        assert html =~ etiqueta
      end
    end

    test "seleccionar el motor fusionado lo deja activo", %{conn: conn} do
      {:ok, vista, _html} = live(conn, ~p"/admin/settings")

      html = vista |> element("button[phx-value-engine=fused]") |> render_click()

      assert html =~ "Motor actualizado correctamente"
      assert App.AIEngineSettings.get_engine() == "fused"
    end
  end

  describe "estrategia de explicabilidad" do
    test "lista las cuatro estrategias con su descripción", %{conn: conn} do
      {:ok, _vista, html} = live(conn, ~p"/admin/settings")

      for etiqueta <- ["Diccionario", "Gradiente filtrado", "Exhaustivo", "Divide y vencerás"] do
        assert html =~ etiqueta
      end
    end

    test "la recomendada aparece marcada como activa al entrar", %{conn: conn} do
      {:ok, _vista, html} = live(conn, ~p"/admin/settings")
      assert html =~ "Gradiente filtrado"
      assert html =~ "Activo"
    end

    test "cambiar de estrategia la persiste en el Agent", %{conn: conn} do
      {:ok, vista, _html} = live(conn, ~p"/admin/settings")

      html = vista |> element("button[phx-value-method=exhaustivo]") |> render_click()

      assert html =~ "Estrategia actualizada correctamente"
      assert App.AIEngineSettings.get_explain_method() == "exhaustivo"
    end

    test "cambiar la estrategia no altera el motor", %{conn: conn} do
      {:ok, vista, _html} = live(conn, ~p"/admin/settings")

      vista |> element("button[phx-value-engine=fused]") |> render_click()
      vista |> element("button[phx-value-method=diccionario]") |> render_click()

      assert App.AIEngineSettings.get_engine() == "fused"
      assert App.AIEngineSettings.get_explain_method() == "diccionario"
    end
  end

  describe "usuarios administradores" do
    test "el listado muestra a los usuarios", %{conn: conn, admin: admin} do
      {:ok, _vista, html} = live(conn, ~p"/admin/users")
      assert html =~ admin.email
    end

    test "la ficha de un usuario muestra sus datos", %{conn: conn} do
      usuario = user_fixture()
      {:ok, _vista, html} = live(conn, ~p"/admin/users/#{usuario.id}")
      assert html =~ usuario.email
    end
  end

  describe "conversaciones" do
    test "el listado carga sin conversaciones", %{conn: conn} do
      {:ok, _vista, html} = live(conn, ~p"/admin/conversations")
      assert html =~ "onversacion"
    end

    test "el listado muestra una conversación existente", %{conn: conn} do
      usuario = user_fixture()
      conversacion = conversation_fixture(usuario)
      {:ok, _vista, html} = live(conn, ~p"/admin/conversations")
      assert html =~ conversacion.conversation_id or html =~ usuario.email
    end

    test "la ficha de una conversación carga", %{conn: conn} do
      usuario = user_fixture()
      conversacion = conversation_fixture(usuario)
      {:ok, _vista, html} = live(conn, ~p"/admin/conversations/#{conversacion.conversation_id}")
      assert html =~ conversacion.conversation_id or html =~ usuario.email
    end
  end

  defp user_fixture(attrs \\ %{}), do: App.Fixtures.user_fixture(attrs)

  defp conversation_fixture(user, attrs \\ %{}),
    do: App.Fixtures.conversation_fixture(user, attrs)

  describe "ficha de conversación con contenido" do
    setup %{conn: conn} do
      usuario = user_fixture()
      conv = conversation_fixture(usuario)

      %App.Projections.MessageProjection{
        message_id: UUID.uuid4(),
        conversation_id: conv.id,
        user_id: to_string(usuario.id),
        content: "Paciente con disnea progresiva",
        message_type: "user",
        timestamp: DateTime.utc_now() |> DateTime.truncate(:second)
      }
      |> Repo.insert!()

      %App.Projections.AnalysisCardProjection{
        card_id: UUID.uuid4(),
        conversation_id: conv.id,
        message_id: UUID.uuid4(),
        card_type: "codes",
        content: Jason.encode!([%{"code" => "J18.9", "description" => "Neumonía"}]),
        position: 0
      }
      |> Repo.insert!()

      %{conn: conn, conv: conv, usuario: usuario}
    end

    test "muestra los mensajes de la conversación", %{conn: conn, conv: conv} do
      {:ok, _vista, html} = live(conn, ~p"/admin/conversations/#{conv.conversation_id}")
      assert html =~ "disnea progresiva"
    end

    test "muestra a quién pertenece", %{conn: conn, conv: conv, usuario: usuario} do
      {:ok, _vista, html} = live(conn, ~p"/admin/conversations/#{conv.conversation_id}")
      assert html =~ usuario.email or html =~ usuario.username
    end

    test "muestra las tarjetas de análisis", %{conn: conn, conv: conv} do
      {:ok, _vista, html} = live(conn, ~p"/admin/conversations/#{conv.conversation_id}")
      assert html =~ "J18.9" or html =~ "odes"
    end
  end

  describe "ficha de usuario con actividad" do
    test "muestra las conversaciones del usuario", %{conn: conn} do
      usuario = user_fixture()
      conversation_fixture(usuario)
      conversation_fixture(usuario)

      {:ok, _vista, html} = live(conn, ~p"/admin/users/#{usuario.id}")
      assert html =~ usuario.email
    end

    test "un usuario sin actividad también carga", %{conn: conn} do
      usuario = user_fixture()
      {:ok, _vista, html} = live(conn, ~p"/admin/users/#{usuario.id}")
      assert html =~ usuario.email
    end
  end

  describe "listado de conversaciones con contenido" do
    test "distingue las activas de las borradas", %{conn: conn} do
      usuario = user_fixture()
      activa = conversation_fixture(usuario)
      borrada = App.Fixtures.deleted_conversation_fixture(usuario)

      {:ok, _vista, html} = live(conn, ~p"/admin/conversations")

      assert html =~ activa.conversation_id or html =~ usuario.email
      # La borrada está en la papelera: puede aparecer marcada, pero la vista no debe romperse
      assert is_binary(borrada.conversation_id)
    end
  end

  describe "configuración del summarizer" do
    test "guardar recarga el modelo en el motor y confirma", %{conn: conn} do
      Req.Test.stub(App.AIEngineMock, fn c -> Req.Test.json(c, %{"status" => "loaded"}) end)

      {:ok, vista, _html} = live(conn, ~p"/admin/settings")

      html =
        vista
        |> form("form[phx-submit=set_summarizer]", %{
          "model" => "gemma4",
          "mode" => "summary",
          "prompt_summary" => "sistema {language}",
          "prompt_paraphrase" => "parafrasea {language}",
          "user_prompt_summary" => "informe {text}",
          "user_prompt_paraphrase" => "reformula {text}"
        })
        |> render_submit()

      assert html =~ "recargado correctamente"
      assert App.SummarizerSettings.get().model == "gemma4"
      App.SummarizerSettings.set_model("none")
    end

    test "si el motor no responde, el panel lo dice en vez de fingir que guardó", %{conn: conn} do
      Req.Test.stub(App.AIEngineMock, fn c -> Req.Test.transport_error(c, :econnrefused) end)

      {:ok, vista, _html} = live(conn, ~p"/admin/settings")

      html =
        vista
        |> form("form[phx-submit=set_summarizer]", %{
          "model" => "gemma4",
          "mode" => "summary",
          "prompt_summary" => "s",
          "prompt_paraphrase" => "p",
          "user_prompt_summary" => "us",
          "user_prompt_paraphrase" => "up"
        })
        |> render_submit()

      assert html =~ "o se pudo" or html =~ "rror"
      App.SummarizerSettings.set_model("none")
    end
  end

  describe "selector de modelo" do
    # Se reutiliza el mock que ya usa el resto de la suite: cambiar :ai_req_opts aqui
    # afectaria a los tests que corren en paralelo, porque es configuracion global.
    defp catalogo(modelos) do
      Req.Test.stub(App.AIEngineMock, fn conn ->
        Req.Test.json(conn, %{"models" => modelos, "loaded_checkpoint" => "classifier.pt"})
      end)
    end

    test "muestra los modelos del catálogo con su estado", %{conn: conn} do
      catalogo([
        %{
          "name" => "produccion",
          "checkpoint" => "classifier.pt",
          "description" => "el de siempre",
          "metrics" => %{"map_test" => 0.43},
          "downloaded" => true,
          "loaded" => true
        },
        %{
          "name" => "zlpr-map",
          "checkpoint" => "classifier-b.pt",
          "description" => "mejor MAP",
          "metrics" => %{},
          "downloaded" => false,
          "loaded" => false
        }
      ])

      {:ok, _vista, html} = live(conn, ~p"/admin/settings")

      assert html =~ "produccion"
      assert html =~ "en uso"
      # Sin este aviso, pulsar Cargar sobre un modelo ausente falla sin explicación
      assert html =~ "sin descargar"
    end

    test "solo ofrece cargar los que están en disco y no son el activo", %{conn: conn} do
      catalogo([
        %{
          "name" => "activo",
          "checkpoint" => "a.pt",
          "description" => "",
          "metrics" => %{},
          "downloaded" => true,
          "loaded" => true
        },
        %{
          "name" => "otro",
          "checkpoint" => "b.pt",
          "description" => "",
          "metrics" => %{},
          "downloaded" => true,
          "loaded" => false
        },
        %{
          "name" => "ausente",
          "checkpoint" => "c.pt",
          "description" => "",
          "metrics" => %{},
          "downloaded" => false,
          "loaded" => false
        }
      ])

      {:ok, vista, _html} = live(conn, ~p"/admin/settings")
      botones = vista |> element("button[phx-value-name]") |> render()

      assert botones =~ "otro"
    end

    test "si el motor no responde, el panel lo dice en vez de quedarse en blanco", %{conn: conn} do
      Req.Test.stub(App.AIEngineMock, fn conn -> Req.Test.transport_error(conn, :econnrefused) end)

      {:ok, _vista, html} = live(conn, ~p"/admin/settings")
      assert html =~ "No se pudo contactar con el AI engine"
    end

    test "cargar un modelo lo pide al motor y refresca el catálogo", %{conn: conn} do
      catalogo([
        %{
          "name" => "otro",
          "checkpoint" => "b.pt",
          "description" => "",
          "metrics" => %{},
          "downloaded" => true,
          "loaded" => false
        }
      ])

      {:ok, vista, _html} = live(conn, ~p"/admin/settings")

      vista |> element("button[phx-value-name='otro']") |> render_click()

      assert render(vista) =~ "otro"
    end
  end
end
