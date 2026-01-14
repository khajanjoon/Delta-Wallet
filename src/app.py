import hashlib
import hmac
import requests
import time
import json
import paho.mqtt.client as mqtt

# ================= DELTA CONFIG =================
BASE_URL = "https://api.india.delta.exchange"
API_KEY = "TcwdPNNYGjjgkRW4BRIAnjL7z5TLyJ"
API_SECRET = "B5ALo5Mh8mgUREB6oGD4oyX3y185oElaz1LoU6Y3X5ZX0s8TvFZcX4YTVToJ"

REFRESH_INTERVAL = 7
# ===============================================

# ================= MQTT CONFIG =================
MQTT_BROKER = "45.120.136.157"
MQTT_PORT = 1883
MQTT_USERNAME = None
MQTT_PASSWORD = None

HA_DISCOVERY_PREFIX = "homeassistant"
BASE_TOPIC = "delta"
# ===============================================


# ---------- HELPERS ----------
def sign(secret, message):
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def auth_headers(method, path):
    ts = str(int(time.time()))
    sig = sign(API_SECRET, method + ts + path)
    return {
        "api-key": API_KEY,
        "timestamp": ts,
        "signature": sig,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }


def fetch_balances():
    path = "/v2/wallet/balances"
    r = requests.get(
        BASE_URL + path,
        headers=auth_headers("GET", path),
        timeout=(3, 27)
    )
    r.raise_for_status()
    return r.json()


def safe_float(v):
    try:
        return float(v)
    except:
        return 0.0


# ================= MQTT INIT (paho v2 FIX) =================
mqttc = mqtt.Client(
    client_id="delta_wallet",
    callback_api_version=mqtt.CallbackAPIVersion.VERSION1
)

if MQTT_USERNAME:
    mqttc.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

mqttc.connect(MQTT_BROKER, MQTT_PORT, 60)
mqttc.loop_start()


# ================= HOME ASSISTANT DISCOVERY =================
def ha_sensor(object_id, name, unit=None, device_class=None):
    topic = f"{HA_DISCOVERY_PREFIX}/sensor/delta/{object_id}/config"

    payload = {
        "name": name,
        "state_topic": f"{BASE_TOPIC}/{object_id}",
        "unique_id": f"delta_{object_id}",
        "value_template": "{{ value | float }}",
        "state_class": "measurement",
        "device": {
            "identifiers": ["delta_exchange"],
            "name": "Delta Exchange Wallet",
            "manufacturer": "Delta Exchange",
            "model": "Wallet API"
        }
    }

    if unit:
        payload["unit_of_measurement"] = unit
    if device_class:
        payload["device_class"] = device_class

    mqttc.publish(topic, json.dumps(payload), retain=True)


# ---------- META SENSORS ----------
ha_sensor(
    "net_equity",
    "Delta Net Equity",
    unit="INR",
    device_class="monetary"
)

ha_sensor(
    "robo_trading_equity",
    "Delta Robo Trading Equity",
    unit="INR",
    device_class="monetary"
)


# ================= MAIN LOOP =================
while True:
    try:
        data = fetch_balances()

        # ---------- META ----------
        meta = data.get("meta", {})

        mqttc.publish(
            f"{BASE_TOPIC}/net_equity",
            f"{safe_float(meta.get('net_equity')):.2f}",
            retain=True
        )

        mqttc.publish(
            f"{BASE_TOPIC}/robo_trading_equity",
            f"{safe_float(meta.get('robo_trading_equity')):.2f}",
            retain=True
        )

        # ---------- ASSET SENSORS ----------
        for b in data.get("result", []):
            asset = b.get("asset_symbol", "").lower()

            for key, val in b.items():
                if key in ("asset_symbol", "id", "user_id"):
                    continue

                sensor_id = f"{asset}_{key}"
                sensor_name = f"{asset.upper()} {key.replace('_', ' ').title()}"

                # Auto-discovery (safe to repeat)
                ha_sensor(
                    sensor_id,
                    sensor_name,
                    unit=asset.upper() if "balance" in key else None
                )

                mqttc.publish(
                    f"{BASE_TOPIC}/{sensor_id}",
                    f"{safe_float(val):.8f}",
                    retain=True
                )

        print("📡 Delta wallet data sent to Home Assistant")

    except KeyboardInterrupt:
        print("\n👋 Stopped safely")
        break
    except Exception as e:
        print("❌ Error:", e)

    time.sleep(REFRESH_INTERVAL)
