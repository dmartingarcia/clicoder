defmodule App.Projections.ProjectorHandlersTest do
  @moduledoc """
  Prueba los manejadores del proyector, no los esquemas.

  El proyector es lo que convierte el registro de eventos en las tablas que lee la interfaz.
  Si un manejador falla, la fuente de verdad sigue siendo correcta pero el usuario ve datos
  distintos de los que hay, que es la clase de error más difícil de diagnosticar en un
  sistema con CQRS.
  """
  use App.DataCase

  alias App.Events.{
    AIPredictionReceived,
    CodeRejected,
    CodeValidated,
    ConversationStarted,
    MessageSent
  }

  alias App.Projections.{
    AnalysisCardProjection,
    ConversationProjection,
    ConversationProjector,
    MessageProjection,
    PredictedCodeProjection
  }

  alias App.Repo

  # El proyector lleva cuenta del último evento procesado y descarta los anteriores, que es
  # su protección contra reprocesar el registro. Los números tienen que ir hacia adelante o
  # el manejador devuelve :ok sin haber escrito nada.
  defp metadata,
    do: %{
      event_number: System.unique_integer([:positive, :monotonic]) + 1_000_000,
      handler_name: "test"
    }

  defp iniciar_conversacion(user_id \\ nil) do
    user = if user_id, do: user_id, else: UUID.uuid4()
    conversation_id = UUID.uuid4()

    :ok =
      ConversationProjector.handle(
        %ConversationStarted{
          conversation_id: conversation_id,
          user_id: user,
          started_at: DateTime.utc_now() |> DateTime.truncate(:second) |> DateTime.to_iso8601()
        },
        metadata()
      )

    {conversation_id, user}
  end

  describe "ConversationStarted" do
    test "crea la conversación en la tabla de lectura" do
      {conversation_id, user_id} = iniciar_conversacion()

      conv = Repo.get_by!(ConversationProjection, conversation_id: conversation_id)
      assert conv.user_id == user_id
      assert conv.status == "active"
    end
  end

  describe "MessageSent" do
    test "añade el mensaje a su conversación" do
      {conversation_id, user_id} = iniciar_conversacion()

      :ok =
        ConversationProjector.handle(
          %MessageSent{
            conversation_id: conversation_id,
            message_id: UUID.uuid4(),
            user_id: user_id,
            content: "Paciente con disnea",
            timestamp: DateTime.utc_now() |> DateTime.truncate(:second) |> DateTime.to_iso8601()
          },
          metadata()
        )

      conv = Repo.get_by!(ConversationProjection, conversation_id: conversation_id)
      mensaje = Repo.get_by!(MessageProjection, conversation_id: conv.id)
      assert mensaje.content == "Paciente con disnea"
    end
  end

  describe "AIPredictionReceived" do
    setup do
      {conversation_id, user_id} = iniciar_conversacion()

      :ok =
        ConversationProjector.handle(
          %AIPredictionReceived{
            conversation_id: conversation_id,
            message_id: UUID.uuid4(),
            cards: [
              %{
                "type" => "codes",
                "card_type" => "codes",
                "card_id" => UUID.uuid4(),
                "content" => "[]",
                "position" => 0
              }
            ],
            predicted_codes: [
              %{
                "code_id" => UUID.uuid4(),
                "code" => "I10",
                "reasoning" => "hipertensión",
                "confidence" => 0.91,
                "status" => "pending"
              }
            ],
            received_at:
              DateTime.utc_now() |> DateTime.truncate(:second) |> DateTime.to_iso8601(),
            engine: "bert"
          },
          metadata()
        )

      conv = Repo.get_by!(ConversationProjection, conversation_id: conversation_id)
      %{conv: conv, conversation_id: conversation_id, user_id: user_id}
    end

    test "persiste la tarjeta de análisis", %{conv: conv} do
      assert Repo.get_by!(AnalysisCardProjection, conversation_id: conv.id).card_type == "codes"
    end

    # Conducta actual, deliberada pero con consecuencias: el proyector NO materializa los
    # códigos predichos, aunque el evento los lleve. Los escribe el canal directamente para
    # poder emitirlos en el acto sin esperar al procesado asíncrono del registro de eventos.
    # El efecto secundario es que esa parte de la tabla de lectura no se reconstruye
    # reproduciendo el registro, que es justo la garantía por la que se eligió CQRS.
    test "no materializa los códigos predichos: los escribe el canal", %{conv: conv} do
      assert Repo.all(PredictedCodeProjection) |> Enum.filter(&(&1.conversation_id == conv.id)) ==
               []
    end
  end

  describe "CodeValidated y CodeRejected" do
    setup do
      {conversation_id, _user_id} = iniciar_conversacion()
      conv = Repo.get_by!(ConversationProjection, conversation_id: conversation_id)
      code_id = UUID.uuid4()

      %PredictedCodeProjection{
        code_id: code_id,
        conversation_id: conv.id,
        cie10_code: "I10",
        reasoning: "hipertensión",
        confidence_score: 0.9,
        status: "pending",
        verified_triggers: []
      }
      |> Repo.insert!()

      %{conversation_id: conversation_id, conv: conv, code_id: code_id}
    end

    test "validar deja el código validado y con autor", ctx do
      :ok =
        ConversationProjector.handle(
          %CodeValidated{
            conversation_id: ctx.conversation_id,
            code_id: ctx.code_id,
            cie10_code: "I10",
            validated_by: "codificador@example.com",
            validation_timestamp:
              DateTime.utc_now() |> DateTime.truncate(:second) |> DateTime.to_iso8601()
          },
          metadata()
        )

      codigo = Repo.get_by!(PredictedCodeProjection, code_id: ctx.code_id)
      assert codigo.status == "validated"
      assert codigo.validated_by == "codificador@example.com"
    end

    test "rechazar guarda el motivo, que es lo que alimenta la retroalimentación", ctx do
      :ok =
        ConversationProjector.handle(
          %CodeRejected{
            conversation_id: ctx.conversation_id,
            code_id: ctx.code_id,
            cie10_code: "I10",
            rejected_by: "codificador@example.com",
            rejection_reason: "el informe no menciona hipertensión",
            rejected_at: DateTime.utc_now() |> DateTime.truncate(:second) |> DateTime.to_iso8601()
          },
          metadata()
        )

      codigo = Repo.get_by!(PredictedCodeProjection, code_id: ctx.code_id)
      assert codigo.status == "rejected"
      assert codigo.rejection_reason == "el informe no menciona hipertensión"
    end
  end

  describe "tolerancia a fallos" do
    test "un evento que no se puede proyectar se salta en vez de tumbar el proyector" do
      # Sin la conversación previa, el manejador no encuentra dónde colgar el mensaje.
      # El proyector debe registrarlo y seguir: pararse dejaría la tabla de lectura
      # congelada para todos los usuarios por un solo evento malo.
      assert ConversationProjector.error({:error, :not_found}, %ConversationStarted{}, %{}) ==
               :skip
    end
  end
end
