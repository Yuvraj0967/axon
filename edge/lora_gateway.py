"""LoRa gateway: validates fixed UART frames, acknowledges them, and forwards to AXON."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sqlite3
import time

import requests

from edge.lora_transport import TransparentUartLora
from shared.lora_protocol import FRAME_SIZE, LoraProtocolError, decode_diagnostic, encode_ack, gateway_diagnostic


class GatewaySpool:
    """Gateway-side de-duplication and delivery journal keyed by (asset, sequence)."""
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.execute("CREATE TABLE IF NOT EXISTS received (asset_id TEXT NOT NULL, sequence INTEGER NOT NULL, diagnostic TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (asset_id, sequence))")
        self.connection.commit()

    def store(self, packet, diagnostic: dict) -> bool:
        import json
        cursor = self.connection.execute("INSERT OR IGNORE INTO received (asset_id, sequence, diagnostic) VALUES (?, ?, ?)", (packet.asset_id, packet.sequence, json.dumps(diagnostic)))
        self.connection.commit()
        return cursor.rowcount == 1

    def deliver_pending(self, api_url: str) -> None:
        import json
        rows = self.connection.execute("SELECT asset_id, sequence, diagnostic FROM received WHERE delivered=0 ORDER BY rowid LIMIT 20").fetchall()
        for asset_id, sequence, raw in rows:
            response = requests.post(f"{api_url.rstrip('/')}/ingest/diagnostic", json=json.loads(raw), timeout=5)
            response.raise_for_status()
            self.connection.execute("UPDATE received SET delivered=1 WHERE asset_id=? AND sequence=?", (asset_id, sequence))
            self.connection.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="AXON transparent-UART LoRa gateway")
    parser.add_argument("--port", default=os.getenv("LORA_SERIAL_PORT", "/dev/serial0"))
    parser.add_argument("--baudrate", type=int, default=int(os.getenv("LORA_BAUDRATE", "9600")))
    parser.add_argument("--api-url", default=os.getenv("BACKEND_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--model-version", default=os.getenv("AXON_BEARING_MODEL_VERSION", "axon-bearing-rf-v1"))
    parser.add_argument("--spool", type=Path, default=Path(os.getenv("AXON_LORA_GATEWAY_DB", "edge/runtime/lora-gateway.sqlite")))
    args = parser.parse_args()
    args.spool.parent.mkdir(parents=True, exist_ok=True)
    radio, spool = TransparentUartLora(args.port, args.baudrate), GatewaySpool(args.spool)
    print(f"LoRa gateway listening on {args.port} at {args.baudrate} baud")
    while True:
        frame = radio.receive(FRAME_SIZE)
        if not frame:
            try:
                spool.deliver_pending(args.api_url)
            except requests.RequestException:
                pass
            continue
        try:
            packet = decode_diagnostic(frame)
            diagnostic = gateway_diagnostic(packet, args.model_version)
            spool.store(packet, diagnostic)
            radio.send(encode_ack(packet.asset_id, packet.sequence))
            spool.deliver_pending(args.api_url)
        except (LoraProtocolError, requests.RequestException, OSError) as exc:
            print(f"ignored or deferred LoRa frame: {exc}")
            time.sleep(0.1)


if __name__ == "__main__":
    main()
