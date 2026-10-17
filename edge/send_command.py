import json, os, sys
import paho.mqtt.client as mqtt

action = sys.argv[1] if len(sys.argv) > 1 else "slow_down"    # slow_down | shutdown | resume
c = mqtt.Client()
c.connect(os.getenv("BROKER_IP", "localhost"), 1883)
c.loop_start()
info = c.publish("factory/M1/command",
                 json.dumps({"machine_id": "M1", "action": action, "issued_by": "test"}))
info.wait_for_publish()
c.loop_stop()
c.disconnect()
print("sent", action)
