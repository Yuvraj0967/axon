# Edge layer (Person 1)

    pip install -r requirements.txt
    python test_health.py               # checks ../shared/health.py
    python simulator.py                 # BROKER_IP env var, default localhost
    python listen.py                    # prints every message on factory/#
    python send_command.py slow_down    # or shutdown / resume

Type `f` + Enter in the simulator terminal to toggle a fault.
See docs/KICKOFF_PERSON1.md for the first-hour checklist.
