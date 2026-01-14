import json
import time
import paho.mqtt.client as mqtt
from delta_rest_client import DeltaRestClient

# ================== DELTA CONFIG ==================
delta_client = DeltaRestClient(
    base_url="https://api.india.delta.exchange",
    api_key="TcwdPNNYGjjgkRW4BRIAnjL7z5TLyJ",
    api_secret="B5ALo5Mh8mgUREB6oGD4oyX3y185oElaz1LoU6Y3X5ZX0s8TvFZcX4YTVToJ",
    raise_for_status=False
)

ASSET_ID = 14  # USD wallet

# ================== MQTT CONFIG ==================
MQTT_BROKER = "45.120.136.157"
MQTT_PORT = 1883
DEVICE_ID = "delta_wallet"

mqttc = mqtt.Client(
    client_id="delta_wallet",
    protocol=mqtt.MQTTv311,
    callback_api_version=mqtt.CallbackAPIVersion.VERSION1
)

mqttc.connect(MQTT_BROKER, MQTT_PORT, 60)

# ================== HELPERS ==================
def is_number(value):
    try:
        float(value)
        return True
    except:
        return False

def guess_unit(key):
    if "inr" in key:
        return "INR"
    if "balance" in key or "margin" in key or "commission" in key:
        return "USD"
    return "USD"

# ================== DISCOVERY FLAG ==================
discovered = False

# ================== UPDATE LOOP ==================
while True:
    try:
        wallet = delta_client.get_balances(ASSET_ID)
        print("💰 Wallet fetched")

        # ---------- AUTO DISCOVERY (RUN ONCE) ----------
        if not discovered:
            for key, value in wallet.items():
                discovery_topic = f"homeassistant/sensor/{DEVICE_ID}/{key}/config"
                state_topic = f"delta/{DEVICE_ID}/{key}"

                payload = {
                    "name": f"Delta {key.replace('_', ' ').title()}",
                    "unique_id": f"{DEVICE_ID}_{key}",
                    "state_topic": state_topic,
                    "icon": "mdi:wallet",
                    "device": {
                        "identifiers": [DEVICE_ID],
                        "name": "Delta Exchange Wallet",
                        "manufacturer": "Delta Exchange",
                        "model": "USD Wallet"
                    }
                }

                # Add units only for numeric sensors
                
                unit = guess_unit(key)
                    
                payload["unit_of_measurement"] = unit

                mqttc.publish(discovery_topic, json.dumps(payload), retain=True)

            discovered = True
            print("✅ MQTT Auto-Discovery for ALL fields completed")

        # ---------- PUBLISH STATES ----------
        for key, value in wallet.items():
            mqttc.publish(
                f"delta/{DEVICE_ID}/{key}",
                value,
                retain=True
            )

        print("🔄 Wallet updated")

    except Exception as e:
        print("❌ Error:", e)

    time.sleep(5)
