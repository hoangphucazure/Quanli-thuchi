from flask import Flask, request
import telebot
import os

app = Flask(__name__)

# Lấy token an toàn
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
bot = telebot.TeleBot(TOKEN, threaded=False) if TOKEN else None

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Chào bạn! Mình là bot chạy trên Vercel 24/24. Hãy gõ gì đó, mình sẽ nhại lại!")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"Bạn vừa nói: {message.text}")

@app.route('/', methods=['GET'])
def index():
    if not TOKEN:
        return "Lỗi: Chưa tìm thấy biến TELEGRAM_TOKEN trên Vercel!", 500
    return "Bot đang hoạt động 🚀", 200

@app.route('/api/webhook', methods=['POST'])
def webhook():
    if not bot:
        return "Bot chưa được cấu hình Token", 500
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200
