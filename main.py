from flask import Flask, request, jsonify
import time
import threading               # ← for non‑blocking off‑timer
import hmac
import hashlib
import requests

app = Flask(__name__)

# ─── 1) YOUR CREDENTIALS ────────────────────────────────────────────────────────
RAZORPAY_WEBHOOK_SECRET = "your_webhook_secret"

# Tuya Smart Plug Credentials
ACCESS_ID = 'ttwa9kmckd7fa43gh93j'
ACCESS_KEY = '29ed6d59223d4241987a2bc5ff5d230d'
DEVICE_ID = 'd71fa3f835cb9557fetwyp'
API_BASE = 'https://openapi.tuya.com'# ← normally unchanged

# ─── 2) VERIFY RAZORPAY SIGNATURE ─────────────────────────────────────────────
def verify_signature(request):
    body         = request.data
    received_sig = request.headers.get('X-Razorpay-Signature')
    generated_sig = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(received_sig, generated_sig)

# ─── 3) TUYA TOKEN & CONTROL HELPERS ──────────────────────────────────────────
def get_tuya_token():
    t        = str(int(time.time() * 1000))
    sign_str = ACCESS_ID + t
    sign     = hmac.new(
        ACCESS_KEY.encode(),
        sign_str.encode(),
        hashlib.sha256
    ).hexdigest().upper()

    headers = {
        'client_id': ACCESS_ID,
        'sign': sign,
        't': t,
        'sign_method': 'HMAC-SHA256'
    }
    r = requests.get(f"{API_BASE}/v1.0/token?grant_type=1", headers=headers)
    return r.json()['result']['access_token']

def control_plug(turn_on=True):
    token = get_tuya_token()
    t     = str(int(time.time() * 1000))
    msg   = ACCESS_ID + token + t
    sign  = hmac.new(
        ACCESS_KEY.encode(),
        msg.encode(),
        hashlib.sha256
    ).hexdigest().upper()

    headers = {
        "client_id": ACCESS_ID,
        "access_token": token,
        "sign": sign,
        "t": t,
        "sign_method": "HMAC-SHA256",
        "Content-Type": "application/json"
    }
    payload = {
        "commands": [{
            "code": "switch_1",
            "value": turn_on
        }]
    }
    requests.post(f"{API_BASE}/v1.0/devices/{DEVICE_ID}/commands",
                  headers=headers, json=payload)

# ─── 4) BACKGROUND TIMER ──────────────────────────────────────────────────────
def delayed_off(delay_secs=1800):
    """Wait then turn the plug off in a separate thread."""
    time.sleep(delay_secs)
    control_plug(False)
    print("Plug OFF (background thread)")

# ─── 5) FLASK ROUTES ───────────────────────────────────────────────────────────
@app.route('/')
def home():
    return "Smart Plug Webhook Server Running!"

@app.route('/razorpay-webhook', methods=['POST'])
def webhook():
    # 5a) Signature check
    if not verify_signature(request):
        return jsonify({"error": "Invalid signature"}), 400

    data = request.get_json()
    # 5b) Event & amount check
    if data.get("event") == "payment.captured":
        amount = data["payload"]["payment"]["entity"]["amount"]
        # ← change this to 3000 for ₹30.00
        if amount == 100:
            control_plug(True)   # turn ON immediately
            print("Plug ON for 30 minutes")
            # spawn a non‑blocking timer to turn it off later
            threading.Thread(target=delayed_off, daemon=True).start()
            return jsonify({"message": "Plug activated"}), 200

    return jsonify({"message": "No action taken"}), 200
@app.route('/test-plug-on', methods=['GET'])
def test_plug_on():
    control_plug(True)
    return jsonify({"message": "Sent ON command to plug"}), 200
if __name__ == '__main__':
    # 5c) Ensure you listen on 0.0.0.0:8000 for Railway
    app.run(host='0.0.0.0', port=8000)
