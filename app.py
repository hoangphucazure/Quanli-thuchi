from flask import Flask, request
import urllib.request
import json
import os
import uuid
import unicodedata
from datetime import datetime, timezone, timedelta
from fpdf import FPDF

app = Flask(__name__)
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
SECRET_KEY = "Phuc2k5@"
VN_TZ = timezone(timedelta(hours=7))

def remove_accents(input_str):
    if not input_str:
        return ""
    s = input_str.replace("đ", "d").replace("Đ", "D")
    nfkd_form = unicodedata.normalize('NFKD', s)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def tg_api(method, payload=None):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"} if payload else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception as e:
        print(f"Loi API {method}:", e)
        return None

# Đăng ký danh sách lệnh để khi gõ "/" sẽ tự động hiện menu
def setup_bot_commands():
    commands = [
        {"command": "thongke", "description": "Xem bang thong ke thu chi va so du"},
        {"command": "pdf", "description": "Xuat phieu bao cao thu chi file PDF"},
        {"command": "xoa", "description": "Xoa giao dich vua nhap gan nhat"},
        {"command": "reset", "description": "Xoa toan bo du lieu lam lai tu dau"},
        {"command": "help", "description": "Xem huong dan su dung bot"}
    ]
    return tg_api("setMyCommands", {"commands": commands})

def send_message(chat_id, text):
    return tg_api("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    })

def send_document(chat_id, file_path, filename, caption=""):
    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    body = []

    for name, val in [("chat_id", str(chat_id)), ("caption", caption)]:
        body.append(f"--{boundary}".encode())
        body.append(f'Content-Disposition: form-data; name="{name}"'.encode())
        body.append(b"")
        body.append(val.encode("utf-8"))

    with open(file_path, "rb") as f:
        file_data = f.read()
    body.append(f"--{boundary}".encode())
    body.append(f'Content-Disposition: form-data; name="document"; filename="{filename}"'.encode())
    body.append(b"Content-Type: application/pdf")
    body.append(b"")
    body.append(file_data)
    body.append(f"--{boundary}--".encode())
    body.append(b"")

    payload = b"\r\n".join(body)
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception as e:
        print("Loi gui PDF:", e)
        return None

def format_money(amount, currency="đ"):
    return f"{amount:,.0f}".replace(",", ".") + (f" {currency}" if currency else "")

def generate_pdf(transactions):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Helvetica", "B", 16)
    now_str = datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M")
    pdf.cell(0, 10, "PHIEU BAO CAO THU CHI CA NHAN", new_x="LMARGIN", new_y="NEXT", align="C")
    
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, f"Ngay xuat phieu: {now_str}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)

    tong_thu = sum(x["amount"] for x in transactions if x["type"] == "THU")
    tong_chi = sum(x["amount"] for x in transactions if x["type"] == "CHI")
    so_du = tong_thu - tong_chi

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(240, 248, 255)
    pdf.cell(0, 8, f"  Tong Thu:  +{format_money(tong_thu, 'd')}", new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.cell(0, 8, f"  Tong Chi:  -{format_money(tong_chi, 'd')}", new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.cell(0, 8, f"  So Du:      {format_money(so_du, 'd')}", new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.ln(7)

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(50, 50, 50)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(12, 8, "STT", border=1, align="C", fill=True)
    pdf.cell(28, 8, "Thoi gian", border=1, align="C", fill=True)
    pdf.cell(35, 8, "Thu / Chi", border=1, align="R", fill=True)
    pdf.cell(35, 8, "So du", border=1, align="R", fill=True)
    pdf.cell(80, 8, "Noi dung", border=1, align="L", fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    running_balance = 0

    for idx, x in enumerate(transactions, 1):
        if x["type"] == "THU":
            running_balance += x["amount"]
            sign = "+"
        else:
            running_balance -= x["amount"]
            sign = "-"

        clean_note = remove_accents(x["note"])
        note = clean_note[:38] + "..." if len(clean_note) > 40 else clean_note

        pdf.cell(12, 8, str(idx), border=1, align="C")
        pdf.cell(28, 8, x["time"], border=1, align="C")
        pdf.cell(35, 8, f"{sign}{format_money(x['amount'], '')} ", border=1, align="R")
        pdf.cell(35, 8, f"{format_money(running_balance, '')} ", border=1, align="R")
        pdf.cell(80, 8, f" {note}", border=1, align="L", new_x="LMARGIN", new_y="NEXT")

    out_path = "/tmp/phieu_thu_chi.pdf"
    pdf.output(out_path)
    return out_path

# Đọc trạng thái xác thực và dữ liệu giao dịch từ tin nhắn ghim
def get_chat_data(chat_id):
    res = tg_api("getChat", {"chat_id": chat_id})
    if res and res.get("ok"):
        pinned = res["result"].get("pinned_message")
        if pinned and "text" in pinned:
            text = pinned["text"]
            if "DATA_JSON:" in text:
                try:
                    json_str = text.split("DATA_JSON:")[1].strip()
                    parsed = json.loads(json_str)
                    # Tương thích ngược với dữ liệu cũ (dạng list)
                    if isinstance(parsed, list):
                        return {"auth": False, "txs": parsed}, pinned["message_id"]
                    return parsed, pinned["message_id"]
                except:
                    pass
    return {"auth": False, "txs": []}, None

# Lưu trạng thái xác thực và dữ liệu giao dịch vào tin nhắn ghim
def save_chat_data(chat_id, data_obj, old_msg_id=None):
    json_str = json.dumps(data_obj, ensure_ascii=False)
    txs = data_obj.get("txs", [])
    msg_text = (
        f"🗄 <b>CƠ SỞ DỮ LIỆU THU CHI</b> (Không xóa tin này)\n"
        f"<i>Trạng thái: Đã xác thực | Giao dịch: {len(txs)}</i>\n\n"
        f"<code>DATA_JSON:{json_str}</code>"
    )
    if old_msg_id:
        res = tg_api("editMessageText", {
            "chat_id": chat_id,
            "message_id": old_msg_id,
            "text": msg_text,
            "parse_mode": "HTML"
        })
        if res and res.get("ok"):
            return
    res = send_message(chat_id, msg_text)
    if res and res.get("ok"):
        new_id = res["result"]["message_id"]
        tg_api("pinChatMessage", {
            "chat_id": chat_id,
            "message_id": new_id,
            "disable_notification": True
        })

def parse_amount(raw_str):
    s = raw_str.lower().strip()
    multiplier = 1
    if s.endswith("k"):
        multiplier = 1000
        s = s[:-1]
    elif s.endswith("tr") or s.endswith("m"):
        multiplier = 1000000
        s = s[:-2] if s.endswith("tr") else s[:-1]
    s = s.replace(".", "").replace(",", "")
    return int(float(s) * multiplier)

def calc_balance(transactions):
    thu = sum(x["amount"] for x in transactions if x["type"] == "THU")
    chi = sum(x["amount"] for x in transactions if x["type"] == "CHI")
    return thu - chi

@app.route('/', methods=['GET'])
def index():
    setup_bot_commands()
    return "Bot Quản Lý Thu Chi (Đã bật khóa Key & Menu lệnh) 🚀", 200

@app.route('/api/webhook', methods=['POST'])
def webhook():
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return "OK", 200

    msg = data["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    if not text:
        return "OK", 200

    chat_data, pinned_id = get_chat_data(chat_id)
    is_auth = chat_data.get("auth", False)
    txs = chat_data.get("txs", [])

    # KIỂM TRA KHÓA BẢO MẬT (KEY)
    if not is_auth:
        if text == SECRET_KEY:
            chat_data["auth"] = True
            save_chat_data(chat_id, chat_data, pinned_id)
            setup_bot_commands()
            send_message(
                chat_id,
                "✅ <b>Xác thực thành công!</b> Chào mừng bạn quay trở lại.\n"
                "Hãy gõ dấu <code>/</code> để xem toàn bộ menu lệnh hoặc nhập <code>+ 100k Lương</code> để bắt đầu."
            )
        else:
            send_message(
                chat_id,
                "🔒 <b>BOT ĐƯỢC BẢO VỆ BẰNG MẬT KHẨU</b>\n\n"
                "Vui lòng nhập chính xác <b>Key kích hoạt</b> để sử dụng các chức năng của bot:"
            )
        return "OK", 200

    # --- CÁC CHỨC NĂNG SAU KHI ĐÃ XÁC THỰC KEY ---
    if text in ["/start", "/help"]:
        setup_bot_commands()
        guide = (
            "💰 <b>BOT QUẢN LÝ THU CHI CÁ NHÂN</b>\n\n"
            "• <b>Nhập Thu:</b> <code>+ 100k Lương</code>\n"
            "• <b>Nhập Chi:</b> <code>- 45k Ăn trưa</code>\n"
            "• <b>Xem thống kê:</b> /thongke\n"
            "• <b>Xuất phiếu PDF:</b> /pdf\n"
            "• <b>Xóa giao dịch vừa nhập:</b> /xoa\n"
            "• <b>Xóa toàn bộ dữ liệu:</b> /reset"
        )
        send_message(chat_id, guide)

    elif text.startswith("+") or text.startswith("-"):
        t_type = "THU" if text.startswith("+") else "CHI"
        content = text[1:].strip()
        parts = content.split(" ", 1)
        try:
            amount = parse_amount(parts[0])
            if amount <= 0:
                raise ValueError()
            note = parts[1].strip() if len(parts) > 1 else "Khong ghi chu"
            now_str = datetime.now(VN_TZ).strftime("%d/%m %H:%M")

            txs.append({
                "type": t_type,
                "amount": amount,
                "note": note,
                "time": now_str
            })
            chat_data["txs"] = txs
            save_chat_data(chat_id, chat_data, pinned_id)

            so_du = calc_balance(txs)
            icon = "🟢" if t_type == "THU" else "🔴"
            sign = "+" if t_type == "THU" else "-"
            reply = (
                f"{icon} <b>Đã ghi nhận: {sign}{format_money(amount)}</b> ({note})\n"
                f"💰 <b>Số dư hiện tại: {format_money(so_du)}</b>"
            )
            send_message(chat_id, reply)
        except:
            send_message(chat_id, "⚠️ Sai cú pháp! Hãy nhập đúng dạng: <code>- 50k Cà phê</code> hoặc <code>+ 100k Lương</code>")

    elif text in ["/thongke", "/tk"]:
        if not txs:
            send_message(chat_id, "📭 Chưa có dữ liệu thu chi nào.")
            return "OK", 200

        tong_thu = sum(x["amount"] for x in txs if x["type"] == "THU")
        tong_chi = sum(x["amount"] for x in txs if x["type"] == "CHI")
        so_du = tong_thu - tong_chi

        recent = txs[-10:]
        lines = []
        for x in reversed(recent):
            sign = "+" if x["type"] == "THU" else "-"
            icon = "🟢" if x["type"] == "THU" else "🔴"
            lines.append(f"{icon} <code>{x['time']}</code> | <b>{sign}{format_money(x['amount'])}</b> ({x['note']})")

        history_text = "\n".join(lines)
        report = (
            f"📊 <b>BẢNG THỐNG KÊ THU CHI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🟢 Tổng Thu:  <b>{format_money(tong_thu)}</b>\n"
            f"🔴 Tổng Chi:  <b>{format_money(tong_chi)}</b>\n"
            f"💰 Số Dư:     <b>{format_money(so_du)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>10 giao dịch gần nhất:</b>\n\n"
            f"{history_text}\n\n"
            f"📄 <i>Bấm /pdf để tải phiếu báo cáo chi tiết</i>"
        )
        send_message(chat_id, report)

    elif text == "/pdf":
        if not txs:
            send_message(chat_id, "📭 Chưa có giao dịch nào để xuất phiếu PDF!")
            return "OK", 200

        try:
            pdf_path = generate_pdf(txs)
            date_tag = datetime.now(VN_TZ).strftime("%d-%m-%Y")
            send_document(chat_id, pdf_path, f"Phieu_Thu_Chi_{date_tag}.pdf", "📄 Phiếu báo cáo thu chi chi tiết của bạn.")
        except Exception as e:
            send_message(chat_id, f"❌ Lỗi khi tạo file PDF: {e}")

    elif text == "/xoa":
        if not txs:
            send_message(chat_id, "📭 Không có giao dịch nào để xóa.")
        else:
            removed = txs.pop()
            chat_data["txs"] = txs
            save_chat_data(chat_id, chat_data, pinned_id)
            so_du = calc_balance(txs)
            send_message(
                chat_id,
                f"🗑 Đã xóa: <b>{removed['type']} {format_money(removed['amount'])}</b> ({removed['note']})\n"
                f"💰 <b>Số dư hiện tại: {format_money(so_du)}</b>"
            )

    elif text == "/reset":
        chat_data["txs"] = []
        save_chat_data(chat_id, chat_data, pinned_id)
        send_message(chat_id, "🔄 Đã xóa sạch toàn bộ dữ liệu thu chi về 0 đ!")

    else:
        send_message(chat_id, "💡 Gõ <code>+ 100k Lương</code> để ghi thu, <code>- 40k Ăn trưa</code> để ghi chi, hoặc gõ dấu <code>/</code> để chọn lệnh.")

    return "OK", 200
