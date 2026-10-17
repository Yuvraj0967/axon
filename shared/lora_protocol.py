"""Compact, fixed-size LoRa diagnostic frames for AXON point-to-point links."""
from __future__ import annotations

import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
import struct
from uuid import uuid4


FRAME_FORMAT = "<HBBBHI"  # asset, component, fault, confidence %, sequence, unix timestamp
FRAME_BODY_SIZE = struct.calcsize(FRAME_FORMAT)  # 11 bytes
FRAME_SIZE = FRAME_BODY_SIZE + 2  # CRC-16/CCITT, 13 bytes total
ACK_BODY_FORMAT = "<HH"  # asset, sequence
ACK_SIZE = struct.calcsize(ACK_BODY_FORMAT) + 2

ASSET_IDS = {"demo-motor-001": 1}
COMPONENT_IDS = {"bearing-drive-end": 1, "bearing-non-drive-end": 2}
FAULT_IDS = {
    "healthy": 0,
    "inner_race_damage": 1,
    "outer_race_damage": 2,
    "rolling_element_damage": 3,
    "other_bearing_damage": 4,
    "unknown": 255,
}


class LoraProtocolError(ValueError):
    """Raised when a fixed LoRa frame is malformed, corrupt, or unsupported."""


def _reverse(values: dict[str, int]) -> dict[int, str]:
    return {value: key for key, value in values.items()}


def crc16(payload: bytes) -> int:
    """CRC-16/CCITT-FALSE; no third-party package is required on the Pi."""
    return binascii.crc_hqx(payload, 0xFFFF)


@dataclass(frozen=True)
class LoraDiagnostic:
    asset_id: str
    component_id: str
    fault_class: str
    confidence_percent: int
    sequence: int
    timestamp: int


def encode_diagnostic(diagnostic: dict, sequence: int) -> bytes:
    """Encode one already-computed Pi diagnostic into the 13-byte radio frame."""
    try:
        asset = ASSET_IDS[diagnostic["asset_id"]]
        component = COMPONENT_IDS[diagnostic["component_id"]]
        fault = FAULT_IDS[diagnostic["fault_class"]]
    except (KeyError, TypeError) as exc:
        raise LoraProtocolError("diagnostic contains an unmapped LoRa identifier") from exc
    confidence = round(float(diagnostic.get("confidence") or 0) * 100)
    timestamp_value = diagnostic.get("timestamp")
    if isinstance(timestamp_value, str):
        timestamp = int(datetime.fromisoformat(timestamp_value.replace("Z", "+00:00")).timestamp())
    else:
        timestamp = int(datetime.now(timezone.utc).timestamp())
    body = struct.pack(FRAME_FORMAT, asset, component, fault, max(0, min(100, confidence)), sequence & 0xFFFF, timestamp)
    return body + struct.pack("<H", crc16(body))


def decode_diagnostic(frame: bytes) -> LoraDiagnostic:
    """Validate and decode a transparent-UART LoRa frame received by the gateway."""
    if len(frame) != FRAME_SIZE:
        raise LoraProtocolError(f"expected {FRAME_SIZE} bytes, received {len(frame)}")
    body, received_crc = frame[:-2], struct.unpack("<H", frame[-2:])[0]
    if crc16(body) != received_crc:
        raise LoraProtocolError("LoRa frame CRC mismatch")
    asset, component, fault, confidence, sequence, timestamp = struct.unpack(FRAME_FORMAT, body)
    try:
        return LoraDiagnostic(_reverse(ASSET_IDS)[asset], _reverse(COMPONENT_IDS)[component], _reverse(FAULT_IDS)[fault], confidence, sequence, timestamp)
    except KeyError as exc:
        raise LoraProtocolError("LoRa frame contains an unsupported identifier") from exc


def encode_ack(asset_id: str, sequence: int) -> bytes:
    try:
        body = struct.pack(ACK_BODY_FORMAT, ASSET_IDS[asset_id], sequence & 0xFFFF)
    except KeyError as exc:
        raise LoraProtocolError("cannot acknowledge an unmapped asset") from exc
    return body + struct.pack("<H", crc16(body))


def ack_matches(frame: bytes, asset_id: str, sequence: int) -> bool:
    if len(frame) != ACK_SIZE:
        return False
    body, received_crc = frame[:-2], struct.unpack("<H", frame[-2:])[0]
    if crc16(body) != received_crc:
        return False
    try:
        asset, acknowledged_sequence = struct.unpack(ACK_BODY_FORMAT, body)
        return _reverse(ASSET_IDS)[asset] == asset_id and acknowledged_sequence == (sequence & 0xFFFF)
    except (KeyError, struct.error):
        return False


def gateway_diagnostic(packet: LoraDiagnostic, model_version: str) -> dict:
    """Expand the radio summary into the typed record accepted by the API."""
    location = {
        "inner_race_damage": "inner_race",
        "outer_race_damage": "outer_race",
        "rolling_element_damage": "rolling_element",
    }.get(packet.fault_class)
    status = "HEALTHY_WITHIN_VALIDATED_SCOPE" if packet.fault_class == "healthy" else "FAULT_SUSPECTED"
    return {
        "event_id": str(uuid4()),
        "timestamp": datetime.fromtimestamp(packet.timestamp, timezone.utc).isoformat(),
        "asset_id": packet.asset_id,
        "component_id": packet.component_id,
        "fault_class": packet.fault_class,
        "fault_location": location,
        "confidence": packet.confidence_percent / 100,
        "confidence_calibrated": False,
        "status": status,
        "evidence": [{"kind": "lora_diagnostic_summary", "source": "lora_uart", "transport": "lora_p2p", "sequence": packet.sequence, "bytes": FRAME_SIZE}],
        "alternative_hypotheses": [],
        "missing_information": ["Probability calibration and physical inspection are required before confirmation."],
        "recommended_confirmation_tests": ["Perform inspection according to equipment-specific authorized documentation."],
        "repair_reference_ids": [],
        "cost_estimate_id": None,
        "model_version": model_version,
        "requires_technician_confirmation": status != "HEALTHY_WITHIN_VALIDATED_SCOPE",
        "simulated": False,
    }
