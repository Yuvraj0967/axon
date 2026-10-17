# Edge layer (Person 1)

    pip install -r requirements.txt
    python test_health.py               # checks ../shared/health.py
    python simulator.py                 # BACKEND_URL env var, default localhost
    python lora_gateway.py              # Raspberry Pi / gateway UART receiver
    python listen.py                    # prints LoRa-backed diagnostic records
    python send_command.py slow_down    # or shutdown / resume

Type `f` + Enter in the simulator terminal to toggle a fault. The bearing path
runs inference on the Raspberry Pi, then sends a 13-byte LoRa summary to the
gateway; the raw vibration window is never transmitted by radio.
See docs/KICKOFF_PERSON1.md for the first-hour checklist.
