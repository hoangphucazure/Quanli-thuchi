from flask import Flask, request
import urllib.request
import json
import os

app = Flask(__name__)
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req)

@app.route('/', methods=['GET'])
def index():
    return "Bot đang hoạt động 🚀", 200

@app.route('/api/webhook', methods=['POST'])
def webhook():
    data = request.get_json(silent=True)
    if data and "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")
        if text == "/start":
            send_message(chat_id, "Chào bạn! Bot đã chạy thành công 24/24!")
        elif text:
            send_message(chat_id, f"Bạn vừa nói: {text}")
    return "OK", 200
