
import json
import paho.mqtt.client as mqtt

# Connect to local Mosquitto broker
client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2
)

client.connect("127.0.0.1", 1883, 60)
client.loop_start()

# Example sensor packet
data = {
    "temperature_c": 23.75,
    "turbidity_adc": 483,
    "ph_simulated": 13.12,
    "ph_is_simulated": True
}

# Convert dictionary to JSON
payload = json.dumps(data)

# Publish to MQTT and wait for delivery
info = client.publish(
    "knighthacks/water",
    payload,
    qos=1
)
info.wait_for_publish(timeout=5)

print("MQTT publish confirmed:", info.is_published())
print(payload)

client.disconnect()
client.loop_stop()
