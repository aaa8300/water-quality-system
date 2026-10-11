"""Knight Hacks IX: MQTT water telemetry to S3 (newline-delimited JSON)."""
import json
import queue
import time
import uuid
from datetime import datetime, timezone

import boto3
import paho.mqtt.client as mqtt

MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "knighthacks/water"
AWS_PROFILE = "knighthacks-uploader"
AWS_REGION = "us-east-2"
S3_BUCKET = "knighthacks-water-telemetry-2026"
S3_PREFIX = "readings/live"
BATCH_INTERVAL = 10
MAX_BATCH_SIZE = 20
RETRY_SECONDS = 10

pending = queue.Queue()


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe(MQTT_TOPIC, qos=1)
        print(f"[MQTT] Connected; subscribed to {MQTT_TOPIC}", flush=True)
    else:
        print(f"[MQTT ERROR] Connection: {reason_code}", flush=True)


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    print(f"[MQTT] Disconnected: {reason_code}", flush=True)


def on_message(client, userdata, message):
    try:
        data = json.loads(message.payload.decode("utf-8"))
        row = {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "temperature_c": float(data["temperature_c"]),
            "turbidity_adc": int(data["turbidity_adc"]),
            "ph_simulated": float(data["ph_simulated"]),
            "ph_is_simulated": True,
        }
        pending.put(row)
        print(f"[SENSOR] {row['temperature_c']} C | turbidity {row['turbidity_adc']} ADC | simulated pH {row['ph_simulated']}", flush=True)
    except (ValueError, TypeError, KeyError, UnicodeDecodeError) as exc:
        print(f"[DATA ERROR] {exc}", flush=True)


def upload_batch(s3, rows):
    # Unique key prevents overwriting earlier batches.
    now = datetime.now(timezone.utc)
    key = f"{S3_PREFIX}/{now:%Y/%m/%d/%H}/batch_{now:%Y%m%dT%H%M%S%fZ}_{uuid.uuid4().hex[:8]}.json"
    # JSON Lines: one JSON object per line, convenient for Databricks JSON ingestion.
    body = ("\n".join(json.dumps(row) for row in rows) + "\n").encode("utf-8")
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=body, ContentType="application/x-ndjson")
    print(f"[S3 SUCCESS] Uploaded {len(rows)} readings to s3://{S3_BUCKET}/{key}", flush=True)


def main():
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    s3 = session.client("s3")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"knighthacks_s3_{uuid.uuid4().hex[:8]}")
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()
    rows = []
    last_upload = time.monotonic()
    next_retry = 0.0
    print("[START] MQTT -> Amazon S3 bridge running", flush=True)
    try:
        while True:
            try:
                rows.append(pending.get(timeout=0.5))
            except queue.Empty:
                pass
            now = time.monotonic()
            if not rows or now < next_retry:
                continue
            if len(rows) < MAX_BATCH_SIZE and now - last_upload < BATCH_INTERVAL:
                continue
            try:
                upload_batch(s3, rows)
                rows.clear()
                last_upload = time.monotonic()
                next_retry = 0.0
            except Exception as exc:
                print(f"[S3 ERROR] {type(exc).__name__}: {exc}", flush=True)
                next_retry = time.monotonic() + RETRY_SECONDS
                print(f"[RETRY] Keeping {len(rows)} readings in memory; retry in {RETRY_SECONDS}s", flush=True)
    except KeyboardInterrupt:
        print(f"\n[STOP] {len(rows)} unsent readings remain in memory", flush=True)
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
