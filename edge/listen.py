import os
import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
    print(msg.topic, msg.payload.decode())

c = mqtt.Client()
c.on_message = on_message
c.connect(os.getenv("BROKER_IP", "localhost"), 1883)
c.subscribe("factory/#")
print("listening on factory/# ...")
c.loop_forever()
