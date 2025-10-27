import json
import requests
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# ----------------------------
# ضع توكن البوت هنا
TOKEN = "8340663836:AAF-bh5hJk-AeaKoZpMyScy4CdVP3SMxegM"

# ملف معلومات السيرفر
SERVER_CONFIG_FILE = "server_info.json"

# تحميل إعدادات السيرفر
with open(SERVER_CONFIG_FILE) as f:
    cfg = json.load(f)
SERVER_HOST = cfg.get("server_host", "127.0.0.1")
SERVER_PORT = cfg.get("server_port", 8080)
ALLOWED_TOKENS = cfg.get("allowed_tokens", [])

SIMULATE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/simulate"

# ----------------------------
def send_to_server(target_ip, port, duration, proto, requester_id):
    headers = {"Content-Type": "application/json"}
    if ALLOWED_TOKENS:
        headers["X-Sim-Token"] = ALLOWED_TOKENS[0]

    payload = {
        "cmd": "fs_simulate",
        "params": {
            "target": target_ip,
            "port": int(port),
            "duration": int(duration),
            "method_used": proto.lower(),
            "_requested_by": {"id": requester_id}
        }
    }

    try:
        r = requests.post(SIMULATE_URL, json=payload, headers=headers, timeout=10)
        return r.text
    except Exception as e:
        return f"خطأ عند إرسال الطلب للسيرفر: {e}"

# ----------------------------
def fs_command(update: Update, context: CallbackContext):
    if len(context.args) != 4:
        update.message.reply_text(
            "استخدم الصيغة:\n/fs <IP> <PORT> <DURATION> <PROTO>"
        )
        return

    target_ip, port, duration, proto = context.args
    requester_id = update.effective_user.id

    result = send_to_server(target_ip, port, duration, proto, requester_id)
    update.message.reply_text(f"نتيجة إرسال الأمر للسيرفر:\n{result}")

# ----------------------------
def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("fs", fs_command))

    print("البوت يعمل الآن... أرسل /fs <IP> <PORT> <DURATION> <PROTO> في تيليجرام")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
