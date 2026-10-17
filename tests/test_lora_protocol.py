from datetime import datetime, timezone

from edge.lora_transport import LoraOutbox, send_pending_once
from shared.lora_protocol import ACK_SIZE, FRAME_SIZE, ack_matches, decode_diagnostic, encode_ack, encode_diagnostic, gateway_diagnostic


def sample_diagnostic():
    return {"asset_id": "demo-motor-001", "component_id": "bearing-drive-end", "fault_class": "other_bearing_damage", "confidence": 0.91, "timestamp": datetime.now(timezone.utc).isoformat()}


def test_lora_frame_is_fixed_size_crc_validated_and_expands_for_the_api():
    frame = encode_diagnostic(sample_diagnostic(), 42)
    assert len(frame) == FRAME_SIZE == 13
    packet = decode_diagnostic(frame)
    assert packet.asset_id == "demo-motor-001" and packet.sequence == 42
    expanded = gateway_diagnostic(packet, "axon-bearing-rf-v1")
    assert expanded["status"] == "FAULT_SUSPECTED"
    assert expanded["evidence"][0]["source"] == "lora_uart"


def test_lora_ack_matches_only_the_correct_asset_and_sequence():
    ack = encode_ack("demo-motor-001", 42)
    assert len(ack) == ACK_SIZE
    assert ack_matches(ack, "demo-motor-001", 42)
    assert not ack_matches(ack, "demo-motor-001", 43)


def test_outbox_retains_a_frame_until_the_gateway_acknowledges_it(tmp_path):
    outbox = LoraOutbox(tmp_path / "outbox.sqlite")
    outbox.queue(sample_diagnostic())

    class Radio:
        def __init__(self): self.frame = None
        def send(self, frame): self.frame = frame
        def receive(self, size):
            packet = decode_diagnostic(self.frame)
            return encode_ack(packet.asset_id, packet.sequence)

    assert send_pending_once(outbox, Radio())
    assert outbox.next_pending() is None
