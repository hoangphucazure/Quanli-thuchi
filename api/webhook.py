from flask import Flask, request
import telebot
import os

TOKEN = os.environ.get("TELEGRAM_TOKEN")
# Bắt buộc phải có threaded=False để không bị lỗi 500 trên Vercel
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Chào bạn! Mình là bot chạy trên Vercel 24/24. Hãy gõ gì đó, mình sẽ nhại lại!")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"Bạn vừa nói: {message.text}")

@app.route('/api/webhook', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def index():
    return "Bot đang hoạt động 🚀", 200
