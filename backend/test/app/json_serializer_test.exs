defmodule App.JsonSerializerTest do
  use App.DataCase, async: true

  alias App.JsonSerializer

  # ---------------------------------------------------------------------------
  # serialize/1
  # ---------------------------------------------------------------------------

  describe "serialize/1" do
    test "encodes a plain map to JSON" do
      term = %{foo: "bar", count: 42}
      result = JsonSerializer.serialize(term)
      assert is_binary(result)
      assert Jason.decode!(result) == %{"foo" => "bar", "count" => 42}
    end

    test "encodes an event struct to JSON" do
      term = %App.Events.ConversationStarted{
        conversation_id: "conv-123",
        user_id: "user-456",
        started_at: nil
      }

      result = JsonSerializer.serialize(term)
      decoded = Jason.decode!(result)

      assert decoded["conversation_id"] == "conv-123"
      assert decoded["user_id"] == "user-456"
    end

    test "encodes a list of maps" do
      term = [%{code: "J45.0", confidence: 0.9}, %{code: "I10", confidence: 0.75}]
      result = JsonSerializer.serialize(term)
      decoded = Jason.decode!(result)

      assert length(decoded) == 2
      assert List.first(decoded)["code"] == "J45.0"
    end

    test "encodes nested maps" do
      term = %{outer: %{inner: %{value: "deep"}}}
      result = JsonSerializer.serialize(term)
      decoded = Jason.decode!(result)

      assert decoded["outer"]["inner"]["value"] == "deep"
    end
  end

  # ---------------------------------------------------------------------------
  # deserialize/2 — with :type config
  # ---------------------------------------------------------------------------

  describe "deserialize/2 with known event type" do
    test "deserializes JSON into the correct struct" do
      json = Jason.encode!(%{
        conversation_id: "conv-abc",
        user_id: "user-xyz",
        started_at: nil
      })

      type = Atom.to_string(App.Events.ConversationStarted)
      result = JsonSerializer.deserialize(json, type: type)

      assert %App.Events.ConversationStarted{} = result
      assert result.conversation_id == "conv-abc"
      assert result.user_id == "user-xyz"
    end

    test "deserializes MessageSent event" do
      json = Jason.encode!(%{
        conversation_id: "conv-1",
        message_id: "msg-1",
        user_id: "user-1",
        content: "Hello",
        timestamp: nil
      })

      type = Atom.to_string(App.Events.MessageSent)
      result = JsonSerializer.deserialize(json, type: type)

      assert %App.Events.MessageSent{} = result
      assert result.content == "Hello"
    end

    test "deserializes a non-map value (list) without struct conversion" do
      json = Jason.encode!(["A", "B", "C"])

      # Even with a type config, non-map values are returned as-is
      type = Atom.to_string(App.Events.ConversationStarted)
      result = JsonSerializer.deserialize(json, type: type)

      assert result == ["A", "B", "C"]
    end
  end

  # ---------------------------------------------------------------------------
  # deserialize/2 — without :type config (metadata path)
  # ---------------------------------------------------------------------------

  describe "deserialize/2 without :type config (metadata deserialization)" do
    test "returns decoded map with atom keys when config is empty" do
      json = Jason.encode!(%{causation_id: "cause-1", correlation_id: "corr-1"})
      result = JsonSerializer.deserialize(json, [])

      assert is_map(result)
      assert result.causation_id == "cause-1"
      assert result.correlation_id == "corr-1"
    end

    test "returns nil for JSON null" do
      json = "null"
      result = JsonSerializer.deserialize(json, [])
      assert is_nil(result)
    end

    test "returns decoded list when JSON is an array" do
      json = Jason.encode!([1, 2, 3])
      result = JsonSerializer.deserialize(json, [])
      assert result == [1, 2, 3]
    end

    test "returns an empty map for empty JSON object" do
      json = "{}"
      result = JsonSerializer.deserialize(json, [])
      assert result == %{}
    end
  end

  # ---------------------------------------------------------------------------
  # Atom keys in nested maps
  # ---------------------------------------------------------------------------

  describe "atom keys in nested structures" do
    test "nested map keys become atoms" do
      json = Jason.encode!(%{
        "cards" => [
          %{"type" => "summary", "content" => "text", "confidence" => 0.9}
        ]
      })

      result = JsonSerializer.deserialize(json, [])

      assert is_list(result.cards)
      [card | _] = result.cards
      # With keys: :atoms, nested keys are also atoms
      assert card.type == "summary"
      assert card.content == "text"
      assert card.confidence == 0.9
    end

    test "deeply nested maps have atom keys" do
      json = Jason.encode!(%{
        "outer" => %{
          "inner" => %{
            "reason" => "test reason",
            "description" => "some description"
          }
        }
      })

      result = JsonSerializer.deserialize(json, [])

      assert result.outer.inner.reason == "test reason"
      assert result.outer.inner.description == "some description"
    end
  end

  # ---------------------------------------------------------------------------
  # Round-trip (serialize then deserialize)
  # ---------------------------------------------------------------------------

  describe "round-trip" do
    test "a map survives serialize → deserialize (metadata path)" do
      original = %{key: "value", number: 7}
      json = JsonSerializer.serialize(original)
      result = JsonSerializer.deserialize(json, [])

      assert result.key == "value"
      assert result.number == 7
    end
  end
end
