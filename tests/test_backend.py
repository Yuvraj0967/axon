from datetime import datetime, timezone
import json

from backend.main import MemoryStore, create_app, handle_mqtt_message


class FakePublisher:
    def __init__(self): self.sent = []
    def publish_command(self, command): self.sent.append(command); return "published"


class Message:
    def __init__(self, topic, payload): self.topic, self.payload = topic, payload


def test_mqtt_ingest_and_api_contract():
    store, publisher = MemoryStore(), FakePublisher()
    now = datetime.now(timezone.utc).isoformat()
    assert handle_mqtt_message(store, Message("factory/M1/telemetry", json.dumps({"machine_id":"M1","ts":now,"temp":73,"vibration":0.3,"current":4.5}).encode()))
    assert handle_mqtt_message(store, Message("factory/M1/alert", json.dumps({"machine_id":"M1","ts":now,"type":"anomaly","score":0.4}).encode()))
    app = create_app(store=store, publisher=publisher, mqtt_enabled=False)
    endpoints = {route.path: route.endpoint for route in app.routes if hasattr(route, "endpoint")}
    assert endpoints["/machines"]() == ["M1"]
    assert len(endpoints["/readings"]("M1", 5)) == 1
    assert len(endpoints["/alerts"]("M1")) == 1
    result = endpoints["/command"](type("Payload", (), {"machine_id":"M1", "action":"slow_down", "issued_by":"test", "model_dump": lambda self: {"machine_id":"M1","action":"slow_down","issued_by":"test"}})())
    assert result["status"] == "published" and publisher.sent[0].action == "slow_down"


def test_malformed_mqtt_message_is_rejected_without_crashing():
    store = MemoryStore()
    assert not handle_mqtt_message(store, Message("factory/M1/telemetry", b"not-json"))
    assert not handle_mqtt_message(store, Message("other/M1/telemetry", b"{}"))
