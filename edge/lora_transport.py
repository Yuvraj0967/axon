"""Reliable transparent-UART LoRa transport for a Raspberry Pi 4 gateway."""
from __future__ import annotations

import sqlite3
from pathlib import Path
import time

from shared.lora_protocol import ACK_SIZE, LoraProtocolError, ack_matches, encode_diagnostic


class LoraOutbox:
    """Persist diagnostic frames before radio transmission and clear them only on ACK."""
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.execute("CREATE TABLE IF NOT EXISTS outbox (sequence INTEGER PRIMARY KEY, asset_id TEXT NOT NULL, frame BLOB NOT NULL, acknowledged INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL)")
        self.connection.execute("CREATE TABLE IF NOT EXISTS sequence_state (id INTEGER PRIMARY KEY CHECK (id = 1), value INTEGER NOT NULL)")
        self.connection.execute("INSERT OR IGNORE INTO sequence_state (id, value) VALUES (1, 0)")
        self.connection.commit()

    def queue(self, diagnostic: dict) -> int:
        sequence = self.connection.execute("SELECT value FROM sequence_state WHERE id=1").fetchone()[0]
        next_sequence = (sequence + 1) & 0xFFFF
        frame = encode_diagnostic(diagnostic, next_sequence)
        self.connection.execute("UPDATE sequence_state SET value=? WHERE id=1", (next_sequence,))
        # The 16-bit sequence counter eventually wraps. Retain unacknowledged
        # frames, but release the old acknowledged slot before its reuse.
        self.connection.execute("DELETE FROM outbox WHERE sequence=? AND acknowledged=1", (next_sequence,))
        self.connection.execute("INSERT INTO outbox (sequence, asset_id, frame, created) VALUES (?, ?, ?, ?)", (next_sequence, diagnostic["asset_id"], frame, time.time()))
        self.connection.commit()
        return next_sequence

    def next_pending(self):
        return self.connection.execute("SELECT sequence, asset_id, frame FROM outbox WHERE acknowledged=0 ORDER BY created LIMIT 1").fetchone()

    def acknowledge(self, sequence: int) -> None:
        self.connection.execute("UPDATE outbox SET acknowledged=1 WHERE sequence=?", (sequence,))
        self.connection.commit()


class TransparentUartLora:
    """Minimal byte transport for Waveshare SX1262/Ebyte E22 transparent mode."""
    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 1.5):
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("Install pyserial on the Raspberry Pi: python -m pip install pyserial==3.5") from exc
        self.serial = serial.Serial(port=port, baudrate=baudrate, timeout=timeout, write_timeout=timeout)

    def send(self, payload: bytes) -> None:
        if self.serial.write(payload) != len(payload):
            raise OSError("LoRa UART write was incomplete")
        self.serial.flush()

    def receive(self, size: int) -> bytes:
        return self.serial.read(size)


def send_pending_once(outbox: LoraOutbox, radio: TransparentUartLora) -> bool:
    """Transmit one persisted frame; it remains queued if no valid ACK returns."""
    pending = outbox.next_pending()
    if not pending:
        return True
    sequence, asset_id, frame = pending
    radio.send(frame)
    acknowledgement = radio.receive(ACK_SIZE)
    if ack_matches(acknowledgement, asset_id, sequence):
        outbox.acknowledge(sequence)
        return True
    return False
