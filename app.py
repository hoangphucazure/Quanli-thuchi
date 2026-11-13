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

def setup_bot_commands():
    commands = [
        {"command": "themloaitien", "description": "Them loai tien moi (VD: /themloaitien Tien xang)"},
        {"command": "xoaloaitien", "description": "Xoa bot loai tien khong dung nua"},
        {"command": "thongke", "description": "Xem bang thong ke thu chi theo loai tien"},
        {"command": "pdf", "description": "Xuat phieu bao cao thu chi file PDF"},
        {"command": "xoa", "description": "Xoa giao dich vua nhap gan nhat"},
        {"command": "reset", "description": "Xoa toan bo giao dich lam lai tu dau"},
        {"command": "help", "description": "Xem huong dan su dung bot"}
    ]
    return tg_api("setMyCommands", {"commands": commands})

def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return tg_api("sendMessage", payload)

def edit_message(chat_id, message_id, text):
    return tg_api("editMessageText", {
        "chat_id": chat_id,
        "message_id": message_id,
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

# Tạo bàn phím hiển thị toàn bộ tag các loại tiền đã thêm
def build_cat_keyboard(categories, prefix, include_all=False):
    keyboard = []
    row = []
    for idx, cat in enumerate(categories):
        row.append({"text": f"🏷 {cat}", "callback_data": f"{prefix}:{idx}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    if include_all:
        keyboard.append([{"text": "📊 Tất cả loại tiền", "callback_data": f"{prefix}:ALL"}])
    return {"inline_keyboard": keyboard}

def generate_pdf(transactions, filter_cat="ALL"):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Helvetica", "B", 15)
    now_str = datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M")
    title = "PHIEU BAO CAO THU CHI" if filter_cat == "ALL" else f"PHIEU THU CHI - {remove_accents(filter_cat).upper()}"
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align="C")
    
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

    # Tiêu đề bảng (Tổng = 190mm)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(50, 50, 50)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(10, 8, "STT", border=1, align="C", fill=True)
    pdf.cell(25, 8, "Thoi gian", border=1, align="C", fill=True)
    pdf.cell(28, 8, "Loai tien", border=1, align="C", fill=True)
    pdf.cell(32, 8, "Thu / Chi", border=1, align="R", fill=True)
    pdf.cell(32, 8, "So du", border=1, align="R", fill=True)
    pdf.cell(63, 8, "Ghi chu", border=1, align="L", fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(0, 0, 0)
    running_balance = 0

    for idx, x in enumerate(transactions, 1):
        if x["type"] == "THU":
            running_balance += x["amount"]
            sign = "+"
        else:
            running_balance -= x["amount"]
            sign = "-"

        clean_cat = remove_accents(x.get("cat", "Khac"))[:14]
        clean_note = remove_accents(x["note"])
        note = clean_note[:30] + "..." if len(clean_note) > 32 else clean_note

        pdf.cell(10, 8, str(idx), border=1, align="C")
        pdf.cell(25, 8, x["time"], border=1, align="C")
        pdf.cell(28, 8, clean_cat, border=1, align="C")
        pdf.cell(32, 8, f"{sign}{format_money(x['amount'], '')} ", border=1, align="R")
        pdf.cell(32, 8, f"{format_money(running_balance, '')} ", border=1, align="R")
        pdf.cell(63, 8, f" {note}", border=1, align="L", new_x="LMARGIN", new_y="NEXT")

    out_path = "/tmp/phieu_thu_chi.pdf"
    pdf.output(out_path)
    return out_path

def get_chat_data(chat_id):
    default_data = {
        "auth": False,
        "cats": ["Tiền chợ", "Tiền nhà", "Lương", "Khác"],
        "pending": None,
        "txs": []
    }
    res = tg_api("getChat", {"chat_id": chat_id})
    if res and res.get("ok"):
        pinned = res["result"].get("pinned_message")
        if pinned and "text" in pinned:
            text = pinned["text"]
            if "DATA_JSON:" in text:
                try:
                    json_str = text.split("DATA_JSON:")[1].strip()
                    parsed = json.loads(json_str)
                    if isinstance(parsed, list):
                        default_data["txs"] = parsed
                        return default_data, pinned["message_id"]
                    default_data.update(parsed)
                    return default_data, pinned["message_id"]
                except:
                    pass
    return default_data, None

def save_chat_data(chat_id, data_obj, old_msg_id=None):
    json_str = json.dumps(data_obj, ensure_ascii=False)
    txs = data_obj.get("txs", [])
    cats = ", ".join(data_obj.get("cats", []))
    msg_text = (
        f"🗄 <b>CƠ SỞ DỮ LIỆU THU CHI</b> (Không xóa tin này)\n"
        f"<i>Loại tiền: {cats} | Giao dịch: {len(txs)}</i>\n\n"
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

def calc_balance(transactions, cat=None):
    filtered = [x for x in transactions if (not cat or x.get("cat") == cat)]
    thu = sum(x["amount"] for x in filtered if x["type"] == "THU")
    chi = sum(x["amount"] for x in filtered if x["type"] == "CHI")
    return thu - chi

def render_stats_text(txs, cat_name="Tất cả loại tiền"):
    tong_thu = sum(x["amount"] for x in txs if x["type"] == "THU")
    tong_chi = sum(x["amount"] for x in txs if x["type"] == "CHI")
    so_du = tong_thu - tong_chi

    recent = txs[-10:]
    lines = []
    for x in reversed(recent):
        sign = "+" if x["type"] == "THU" else "-"
        icon = "🟢" if x["type"] == "THU" else "🔴"
        c_tag = f"[{x.get('cat', 'Khác')}] " if cat_name == "Tất cả loại tiền" else ""
        note_str = f" ({x['note']})" if x.get("note") and x["note"] != "Khong ghi chu" else ""
        lines.append(f"{icon} <code>{x['time']}</code> | <b>{sign}{format_money(x['amount'])}</b> {c_tag}{note_str}")

    history_text = "\n".join(lines) if lines else "<i>Chưa có giao dịch nào</i>"
    return (
        f"📊 <b>THỐNG KÊ: {cat_name.upper()}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 Tổng Thu:  <b>{format_money(tong_thu)}</b>\n"
        f"🔴 Tổng Chi:  <b>{format_money(tong_chi)}</b>\n"
        f"💰 Số Dư:     <b>{format_money(so_du)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>Giao dịch gần nhất:</b>\n\n"
        f"{history_text}"
    )

@app.route('/', methods=['GET'])
def index():
    setup_bot_commands()
    return "đang hoạt động", 200

@app.route('/api/webhook', methods=['POST'])
def webhook():
    data = request.get_json(silent=True)
    if not data:
        return "OK", 200

    # ==========================================
    # XỬ LÝ KHI BẤM CHỌN TAG LOẠI TIỀN
    # ==========================================
    if "callback_query" in data:
        cb = data["callback_query"]
        cb_id = cb["id"]
        chat_id = cb["message"]["chat"]["id"]
        msg_id = cb["message"]["message_id"]
        cb_data = cb.get("data", "")

        tg_api("answerCallbackQuery", {"callback_query_id": cb_id})
        chat_data, pinned_id = get_chat_data(chat_id)
        if not chat_data.get("auth"):
            return "OK", 200

        cats = chat_data.get("cats", ["Tiền chợ", "Tiền nhà", "Lương", "Khác"])
        txs = chat_data.get("txs", [])

        if ":" not in cb_data:
            return "OK", 200

        action, val = cb_data.split(":", 1)

        # Xóa loại tiền
        if action == "DELCAT":
            idx = int(val)
            if 0 <= idx < len(cats):
                removed_cat = cats.pop(idx)
                chat_data["cats"] = cats
                save_chat_data(chat_id, chat_data, pinned_id)
                edit_message(chat_id, msg_id, f"🗑 Đã xóa loại tiền: <b>{removed_cat}</b>")
            return "OK", 200

        selected_cat = "ALL" if val == "ALL" else cats[int(val)]

        # 1. Lưu giao dịch sau khi người dùng ấn chọn tag loại tiền
        if action == "TX":
            pending = chat_data.get("pending")
            if not pending:
                edit_message(chat_id, msg_id, "⚠️ Giao dịch này đã được xử lý hoặc hết hạn.")
                return "OK", 200

            pending["cat"] = selected_cat
            txs.append(pending)
            chat_data["txs"] = txs
            chat_data["pending"] = None
            save_chat_data(chat_id, chat_data, pinned_id)

            tong_so_du = calc_balance(txs)
            icon = "🟢" if pending["type"] == "THU" else "🔴"
            sign = "+" if pending["type"] == "THU" else "-"
            note_display = f" ({pending['note']})" if pending.get("note") and pending["note"] != "Khong ghi chu" else ""

            reply = (
                f"{icon} <b>Đã lưu: {sign}{format_money(pending['amount'])}</b>{note_display}\n"
                f"🏷 Loại tiền: <b>{selected_cat}</b>\n"
                f"💰 <b>Số dư hiện tại: {format_money(tong_so_du)}</b>"
            )
            edit_message(chat_id, msg_id, reply)

        # 2. Xem Thống kê theo loại tiền đã chọn
        elif action == "STAT":
            if selected_cat == "ALL":
                report = render_stats_text(txs, "Tất cả loại tiền")
            else:
                filtered = [x for x in txs if x.get("cat") == selected_cat]
                report = render_stats_text(filtered, selected_cat)
            edit_message(chat_id, msg_id, report)

        # 3. Xuất PDF theo loại tiền đã chọn
        elif action == "PDF":
            if selected_cat == "ALL":
                filtered = txs
                label = "Tat_Ca"
            else:
                filtered = [x for x in txs if x.get("cat") == selected_cat]
                label = remove_accents(selected_cat).replace(" ", "_")

            if not filtered:
                edit_message(chat_id, msg_id, f"📭 Loại tiền <b>{selected_cat}</b> chưa có giao dịch nào để xuất PDF!")
                return "OK", 200

            edit_message(chat_id, msg_id, f"⏳ Đang xuất phiếu PDF cho <b>{selected_cat}</b>...")
            pdf_path = generate_pdf(filtered, selected_cat)
            date_tag = datetime.now(VN_TZ).strftime("%d-%m-%Y")
            send_document(chat_id, pdf_path, f"Phieu_{label}_{date_tag}.pdf", f"📄 Phiếu báo cáo thu chi: {selected_cat}")

        return "OK", 200

    # ==========================================
    # XỬ LÝ TIN NHẮN VĂN BẢN
    # ==========================================
    if "message" not in data:
        return "OK", 200

    msg = data["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    if not text:
        return "OK", 200

    chat_data, pinned_id = get_chat_data(chat_id)
    is_auth = chat_data.get("auth", False)
    txs = chat_data.get("txs", [])
    cats = chat_data.get("cats", ["Tiền chợ", "Tiền nhà", "Lương", "Khác"])

    # KIỂM TRA KHÓA BẢO MẬT (KEY)
    if not is_auth:
        if text == SECRET_KEY:
            chat_data["auth"] = True
            save_chat_data(chat_id, chat_data, pinned_id)
            setup_bot_commands()
            send_message(
                chat_id,
                "✅ <b>Xác thực thành công!</b>\n"
                "Hãy gõ dấu <code>/</code> để xem toàn bộ menu lệnh hoặc nhập <code>+100k</code> để bắt đầu."
            )
        else:
            send_message(
                chat_id,
                "🔒 <b>BOT ĐƯỢC BẢO VỆ BẰNG MẬT KHẨU</b>\n\n"
                "Vui lòng nhập chính xác <b>Key kích hoạt</b> để sử dụng:"
            )
        return "OK", 200

    # 1. Hướng dẫn
    if text in ["/start", "/help"]:
        setup_bot_commands()
        cats_str = ", ".join([f"<code>{c}</code>" for c in cats])
        guide = (
            "💰 <b>BOT QUẢN LÝ THU CHI CÁ NHÂN</b>\n\n"
            f"🏷 <b>Các loại tiền hiện có:</b> {cats_str}\n\n"
            "• <b>Thêm loại tiền mới:</b> <code>/themloaitien Tiền xăng</code>\n"
            "• <b>Xóa bớt loại tiền:</b> /xoaloaitien\n"
            "• <b>Nhập Thu:</b> <code>+100k</code> hoặc <code>+100k thưởng</code>\n"
            "• <b>Nhập Chi:</b> <code>-50k</code> hoặc <code>-50k mua rau</code>\n"
            "• <b>Xem thống kê:</b> /thongke\n"
            "• <b>Xuất phiếu PDF:</b> /pdf\n"
            "• <b>Xóa giao dịch gần nhất:</b> /xoa\n"
            "• <b>Reset toàn bộ:</b> /reset"
        )
        send_message(chat_id, guide)

    # 2. Thêm loại tiền mới (/themloaitien Tên)
    elif text.startswith("/themloaitien"):
        new_cat = text.replace("/themloaitien", "", 1).strip()
        if not new_cat:
            cats_str = "\n".join([f"• {c}" for c in cats])
            send_message(
                chat_id,
                f"🏷 <b>Danh sách loại tiền hiện tại:</b>\n{cats_str}\n\n"
                f"👉 Để thêm loại mới, hãy gõ: <code>/themloaitien Tên loại tiền</code>\n"
                f"<i>Ví dụ: <code>/themloaitien Tiền xăng</code></i>"
            )
            return "OK", 200

        if new_cat in cats:
            send_message(chat_id, f"⚠️ Loại tiền <b>{new_cat}</b> đã tồn tại rồi!")
        else:
            if "Khác" in cats:
                idx_khac = cats.index("Khác")
                cats.insert(idx_khac, new_cat)
            else:
                cats.append(new_cat)
            chat_data["cats"] = cats
            save_chat_data(chat_id, chat_data, pinned_id)
            send_message(chat_id, f"✅ Đã thêm loại tiền mới: <b>{new_cat}</b>")

    # 2b. Xóa loại tiền (/xoaloaitien)
    elif text == "/xoaloaitien":
        if len(cats) <= 1:
            send_message(chat_id, "⚠️ Phải giữ lại ít nhất 1 loại tiền!")
            return "OK", 200
        kb = build_cat_keyboard(cats, "DELCAT", include_all=False)
        send_message(chat_id, "🗑 Bấm chọn <b>loại tiền</b> bạn muốn xóa:", reply_markup=kb)

    # 3. Nhập Thu (+) hoặc Chi (-) -> LUÔN HỎI LOẠI TIỀN TRƯỚC VÀ HIỆN TAG ĐỂ BẤM
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

            # Lưu tạm giao dịch chờ bấm tag
            chat_data["pending"] = {
                "type": t_type,
                "amount": amount,
                "note": note,
                "time": now_str
            }
            save_chat_data(chat_id, chat_data, pinned_id)

            sign = "+" if t_type == "THU" else "-"
            note_hint = f" (<i>{note}</i>)" if note != "Khong ghi chu" else ""
            kb = build_cat_keyboard(cats, "TX", include_all=False)
            send_message(
                chat_id,
                f"❓ Khoản <b>{sign}{format_money(amount)}</b>{note_hint} là <b>tiền gì</b>?\n"
                f"👇 <i>Bấm chọn loại tiền bên dưới:</i>",
                reply_markup=kb
            )
        except:
            send_message(chat_id, "⚠️ Sai cú pháp! Hãy nhập đúng dạng: <code>+100k</code> hoặc <code>-50k mua rau</code>")

    # 4. Xem Thống kê -> Hỏi chọn loại tiền trước
    elif text in ["/thongke", "/tk"]:
        if not txs:
            send_message(chat_id, "📭 Chưa có dữ liệu thu chi nào.")
            return "OK", 200
        kb = build_cat_keyboard(cats, "STAT", include_all=True)
        send_message(chat_id, "📊 Bạn muốn xem thống kê của <b>loại tiền</b> nào?", reply_markup=kb)

    # 5. Xuất PDF -> Hỏi chọn loại tiền trước
    elif text == "/pdf":
        if not txs:
            send_message(chat_id, "📭 Chưa có giao dịch nào để xuất phiếu PDF!")
            return "OK", 200
        kb = build_cat_keyboard(cats, "PDF", include_all=True)
        send_message(chat_id, "📄 Bạn muốn xuất phiếu PDF cho <b>loại tiền</b> nào?", reply_markup=kb)

    # 6. Xóa giao dịch gần nhất
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
                f"🗑 Đã xóa: <b>{removed['type']} {format_money(removed['amount'])}</b> [{removed.get('cat', 'Khác')}]\n"
                f"💰 <b>Số dư hiện tại: {format_money(so_du)}</b>"
            )

    # 7. Reset toàn bộ
    elif text == "/reset":
        chat_data["txs"] = []
        chat_data["pending"] = None
        save_chat_data(chat_id, chat_data, pinned_id)
        send_message(chat_id, "🔄 Đã xóa sạch toàn bộ giao dịch về 0 đ!")

    else:
        send_message(chat_id, "💡 Gõ <code>+100k</code> hoặc <code>-50k</code> để nhập thu chi, hoặc gõ dấu <code>/</code> để chọn lệnh.")

    return "OK", 200
