# Databricks notebook source
# DBTITLE 1,MQTT Sensor Data Import
# MAGIC %md
# MAGIC # MQTT Live Sensor Data Import
# MAGIC
# MAGIC This notebook connects to an MQTT broker to subscribe to live sensor data streams and imports them into Databricks for storage and analysis.

# COMMAND ----------

# DBTITLE 1,Install paho-mqtt
# MAGIC %pip install paho-mqtt

# COMMAND ----------

# DBTITLE 1,Connect to MQTT broker and collect sensor data
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import json
import time
from datetime import datetime, timezone

# ===== MQTT Configuration — Fill in your broker details =====
MQTT_BROKER = "your-broker.example.com"   # e.g. "broker.hivemq.com", "test.mosquitto.org"
MQTT_PORT = 1883                          # 1883 = unencrypted, 8883 = TLS/SSL
MQTT_TOPIC = "sensors/#"                   # Topic filter (use # as multi-level wildcard)
MQTT_USERNAME = ""                        # Set to "" if no authentication
MQTT_PASSWORD = ""                        # Set to "" if no authentication
COLLECTION_DURATION_SECONDS = 30          # How long to collect messages
# ==============================================================

messages = []

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        print(f"Subscribed to topic: {MQTT_TOPIC}")
    else:
        print(f"Failed to connect, return code: {reason_code}")

def on_message(client, userdata, message):
    timestamp = datetime.now(timezone.utc).isoformat()
    topic = message.topic
    try:
        payload = json.loads(message.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {"raw": message.payload.decode("utf-8", errors="replace")}
    
    record = {
        "timestamp": timestamp,
        "topic": topic,
        "payload": payload,
    }
    messages.append(record)
    print(f"[{timestamp}] {topic}: {payload}")

# Create and configure client
client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
if MQTT_USERNAME:
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

client.on_connect = on_connect
client.on_message = on_message

# Connect and start collecting
print(f"Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
client.connect(MQTT_BROKER, MQTT_PORT)
client.loop_start()

print(f"Collecting messages for {COLLECTION_DURATION_SECONDS} seconds...")
time.sleep(COLLECTION_DURATION_SECONDS)

client.loop_stop()
client.disconnect()
print(f"\nCollected {len(messages)} messages.")

# COMMAND ----------

# DBTITLE 1,Convert to Spark DataFrame and save
if messages:
    # Convert collected messages to a Spark DataFrame
    df = spark.createDataFrame(messages)
    display(df)
    
    # Optionally write to a Delta table — uncomment to persist
    # df.write.format("delta").mode("append").saveAsTable("sensors.mqtt_raw_data")
    # print("Data written to Delta table: sensors.mqtt_raw_data")
else:
    print("No messages were collected. Check your MQTT broker configuration.")