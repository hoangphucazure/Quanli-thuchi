from flask import Flask, request
import urllib.request
import urllib.parse
import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from fpdf import FPDF

app = Flask(__name__)
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
VN_TZ = timezone(timedelta(hours=7))

def tg_api(method, payload=None):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"} if payload else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception as e:
        print(f"Lỗi API {method}:", e)
        return None

def send_message(chat_id, text):
    return tg_api("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    })

# Hàm gửi file tài liệu (PDF) lên Telegram bằng multipart/form-data
def send_document(chat_id, file_path, filename, caption=""):
    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    body = []

    # Thêm chat_id và caption
    for name, val in [("chat_id", str(chat_id)), ("caption", caption)]:
        body.append(f"--{boundary}".encode())
        body.append(f'Content-Disposition: form-data; name="{name}"'.encode())
        body.append(b"")
        body.append(val.encode("utf-8"))

    # Thêm file PDF
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
        print("Lỗi gửi PDF:", e)
        return None

# Tải font tiếng Việt (DejaVuSans) vào thư mục tạm /tmp của Vercel
def get_vn_font():
    font_path = "/tmp/DejaVuSans.ttf"
    if not os.path.exists(font_path):
        font_url = "https://github.com/matomo-org/travis-scripts/raw/master/fonts/DejaVuSans.ttf"
        urllib.request.urlretrieve(font_url, font_path)
    return font_path

# Tạo file PDF báo cáo thu chi
def generate_pdf(transactions):
    pdf = FPDF()
    pdf.add_page()
    font_path = get_vn_font()
    pdf.add_font("DejaVu", "", font_path, uni=True)
    pdf.set_font("DejaVu", size=16)

    now_str = datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M")
    pdf.cell(0, 10, "PHIẾU BÁO CÁO THU CHI CÁ NHÂN", ln=True, align="C")
    pdf.set_font("DejaVu", size=10)
    pdf.cell(0, 8, f"Ngày xuất phiếu: {now_str}", ln=True, align="C")
    pdf.ln(5)

    tong_thu = sum(x["amount"] for x in transactions if x["type"] == "THU")
    tong_chi = sum(x["amount"] for x in transactions if x["type"] == "CHI")
    so_du = tong_thu - tong_chi

    # Khung tổng kết
    pdf.set_font("DejaVu", size=11)
    pdf.set_fill_color(240, 248, 255)
    pdf.cell(0, 9, f"  Tổng Thu:  +{format_money(tong_thu)}", ln=True, fill=True)
    pdf.cell(0, 9, f"  Tổng Chi:  -{format_money(tong_chi)}", ln=True, fill=True)
    pdf.cell(0, 9, f"  Số Dư:      {format_money(so_du)}", ln=True, fill=True)
    pdf.ln(8)

    # Tiêu đề bảng chi tiết
    pdf.set_font("DejaVu", size=10)
    pdf.set_fill_color(50, 50, 50)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(15, 9, "STT", border=1, align="C", fill=True)
    pdf.cell(35, 9, "Thời gian", border=1, align="C", fill=True)
    pdf.cell(20, 9, "Loại", border=1, align="C", fill=True)
    pdf.cell(45, 9, "Số tiền", border=1, align="R", fill=True)
    pdf.cell(75, 9, "Nội dung ghi chú", border=1, align="L", fill=True)
    pdf.ln()

    # Dữ liệu từng dòng
    pdf.set_text_color(0, 0, 0)
    for idx, x in enumerate(transactions, 1):
        sign = "+" if x["type"] == "THU" else "-"
        note = x["note"][:32] + "..." if len(x["note"]) > 35 else x["note"]
        pdf.cell(15, 8, str(idx), border=1, align="C")
        pdf.cell(35, 8, x["time"], border=1, align="C")
        pdf.cell(20, 8, x["type"], border=1, align="C")
        pdf.cell(45, 8, f"{sign}{format_money(x['amount'])}", border=1, align="R")
        pdf.cell(75, 8, f" {note}", border=1, align="L")
        pdf.ln()

    out_path = "/tmp/phieu_thu_chi.pdf"
    pdf.output(out_path)
    return out_path

def get_transactions(chat_id):
    res = tg_api("getChat", {"chat_id": chat_id})
    if res and res.get("ok"):
        pinned = res["result"].get("pinned_message")
        if pinned and "text" in pinned:
            text = pinned["text"]
            if "DATA_JSON:" in text:
                try:
                    json_str = text.split("DATA_JSON:")[1].strip()
                    return json.loads(json_str), pinned["message_id"]
                except:
                    pass
    return [], None

def save_transactions(chat_id, transactions, old_msg_id=None):
    json_str = json.dumps(transactions, ensure_ascii=False)
    msg_text = (
        f"🗄 <b>CƠ SỞ DỮ LIỆU THU CHI</b> (Không xóa tin này)\n"
        f"<i>Tổng số giao dịch đã lưu: {len(transactions)}</i>\n\n"
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

def format_money(amount):
    return f"{amount:,.0f}".replace(",", ".") + " đ"

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

@app.route('/', methods=['GET'])
def index():
    return "Bot Quản Lý Thu Chi + Xuất PDF đang hoạt động 🚀", 200

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

    if text in ["/start", "/help"]:
        guide = (
            "💰 <b>BOT QUẢN LÝ THU CHI CÁ NHÂN</b>\n\n"
            "• <b>Nhập Thu:</b> <code>+ 15tr Lương tháng</code>\n"
            "• <b>Nhập Chi:</b> <code>- 45k Ăn trưa</code>\n"
            "• <b>Xem thống kê nhanh:</b> <code>/thongke</code> (hoặc <code>/tk</code>)\n"
            "• <b>Xuất phiếu báo cáo PDF:</b> <code>/pdf</code>\n"
            "• <b>Xóa giao dịch vừa nhập:</b> <code>/xoa</code>\n"
            "• <b>Xóa toàn bộ dữ liệu:</b> <code>/reset</code>"
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
            note = parts[1].strip() if len(parts) > 1 else "Không ghi chú"
            now_str = datetime.now(VN_TZ).strftime("%d/%m %H:%M")

            txs, pinned_id = get_transactions(chat_id)
            txs.append({
                "type": t_type,
                "amount": amount,
                "note": note,
                "time": now_str
            })
            save_transactions(chat_id, txs, pinned_id)

            icon = "🟢" if t_type == "THU" else "🔴"
            reply = (
                f"{icon} <b>Đã ghi nhận khoản {t_type}:</b>\n"
                f"• Số tiền: <b>{format_money(amount)}</b>\n"
                f"• Nội dung: {note}\n"
                f"• Thời gian: {now_str}"
            )
            send_message(chat_id, reply)
        except:
            send_message(chat_id, "⚠️ Sai cú pháp! Hãy nhập đúng dạng: <code>- 50k Cà phê</code> hoặc <code>+ 10tr Lương</code>")

    elif text in ["/thongke", "/tk"]:
        txs, _ = get_transactions(chat_id)
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
            f"📄 <i>Gõ /pdf để tải toàn bộ phiếu báo cáo dạng file PDF</i>"
        )
        send_message(chat_id, report)

    elif text == "/pdf":
        txs, _ = get_transactions(chat_id)
        if not txs:
            send_message(chat_id, "📭 Chưa có giao dịch nào để xuất phiếu PDF!")
            return "OK", 200

        send_message(chat_id, "⏳ Đang tạo phiếu thu chi PDF, vui lòng đợi vài giây...")
        try:
            pdf_path = generate_pdf(txs)
            date_tag = datetime.now(VN_TZ).strftime("%d-%m-%Y")
            send_document(chat_id, pdf_path, f"Phieu_Thu_Chi_{date_tag}.pdf", "📄 Phiếu báo cáo thu chi chi tiết của bạn.")
        except Exception as e:
            send_message(chat_id, f"❌ Lỗi khi tạo file PDF: {e}")

    elif text == "/xoa":
        txs, pinned_id = get_transactions(chat_id)
        if not txs:
            send_message(chat_id, "📭 Không có giao dịch nào để xóa.")
        else:
            removed = txs.pop()
            save_transactions(chat_id, txs, pinned_id)
            send_message(chat_id, f"🗑 Đã xóa giao dịch gần nhất: <b>{removed['type']} {format_money(removed['amount'])}</b> ({removed['note']})")

    elif text == "/reset":
        _, pinned_id = get_transactions(chat_id)
        save_transactions(chat_id, [], pinned_id)
        send_message(chat_id, "🔄 Đã xóa sạch toàn bộ dữ liệu thu chi về 0!")

    else:
        send_message(chat_id, "💡 Gõ <code>+ 500k Lương</code> để ghi thu, <code>- 40k Ăn trưa</code> để ghi chi, <code>/tk</code> để xem thống kê hoặc <code>/pdf</code> để xuất file PDF.")

    return "OK", 200
