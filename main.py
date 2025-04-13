from flask import Flask, request, jsonify
import time
import hmac
import hashlib
import requests

app = Flask(__name__)

# ---- Credentials (replace with your real ones) ----
RAZORPAY_WEBHOOK_SECRET = "your_webhook_secret"
ACCESS_ID = "your_tuya_access_id"
ACCESS_KEY = "your_tuya_access_secret"
DEVICE_ID = "your_tuya_device_id"
API_BASE = 'https://openapi.tuya.com'

# Verify Razorpay signature
def verify_signature(request):
    body = request.data
    received_sig = request.headers.get('X-Razorpay-Signature')
    generated_sig = hmac.new(RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(received_sig, generated_sig)

# Get Tuya Token
def get_tuya_token():
    t = str(int(time.time() * 1000))
    sign_str = ACCESS_ID + t
    sign = hmac.new(ACCESS_KEY.encode(), sign_str.encode(), hashlib.sha256).hexdigest().upper()
    headers = {
        'client_id': ACCESS_ID,
        'sign': sign,
        't': t,
        'sign_method': 'HMAC-SHA256'
    }
    r = requests.get(API_BASE + '/v1.0/token?grant_type=1', headers=headers)
    return r.json()['result']['access_token']

# Control the plug
def control_plug(turn_on=True):
    token = get_tuya_token()
    t = str(int(time.time() * 1000))
    msg = ACCESS_ID + token + t
    sign = hmac.new(ACCESS_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest().upper()
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
    url = f"{API_BASE}/v1.0/devices/{DEVICE_ID}/commands"
    requests.post(url, headers=headers, json=payload)

@app.route('/')
def home():
    return "Smart Plug Webhook Server Running!"

@app.route('/razorpay-webhook', methods=['POST'])
def webhook():
    if not verify_signature(request):
        return jsonify({"error": "Invalid signature"}), 400

    data = request.get_json()
    if data.get("event") == "payment.captured":
        amount = data["payload"]["payment"]["entity"]["amount"]
        if amount == 100:  # ₹30 in paise
            control_plug(True)
            print("Plug ON for 30 minutes")
            time.sleep(1800)
            control_plug(False)
            print("Plug OFF")
            return jsonify({"message": "Plug activated"}), 200

    return jsonify({"message": "Payment received"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
