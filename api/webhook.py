from flask import Flask, request
import telebot
import os

# Lấy token từ biến môi trường của Vercel
TOKEN = os.environ.get("8933846699:AAH4gvGgDyGyHMo-HXiVGKgV4qxmOsOUbAE")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Xử lý lệnh /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Chào bạn! Mình là bot chạy trên Vercel. Hãy gõ gì đó, mình sẽ nhại lại!")

# Xử lý mọi tin nhắn văn bản khác (nhại lại tin nhắn)
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"Bạn vừa nói: {message.text}")

# Route này nhận dữ liệu từ Telegram gửi về
@app.route('/api/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

# Route trang chủ để kiểm tra web có sống không
@app.route('/')
def index():
    return "Bot đang hoạt động 🚀"