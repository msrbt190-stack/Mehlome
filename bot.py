#!/usr/bin/env python3
# fs_sim_bot.py
# بوت تليجرام لمحاكاة أمر /fs -> يبني JSON شبيه بالمخرجات التي عرضتها ويرسله لسيرفر محاكي (إن وُجد).
# DOES NOT perform any real network attacks.
#
# متطلبات:
#   pip install python-telegram-bot requests
#
# ملاحظة أمان: التوكن والمُعرّف مضمّنان كما طلبت. يُفضل لاحقًا وضع التوكن في متغير بيئة.

import os
import json
import time
import logging
import ipaddress
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --------- CONFIG (مضمّن كما طلبت) ----------
BOT_TOKEN = "8340663836:AAF-bh5hJk-AeaKoZpMyScy4CdVP3SMxegM"
OWNER_ID = 1605954508

# قائمة البورتات الثابتة المسموح بها
ALLOWED_PORTS = {32000, 32001, 32002, 32003}

# ملف الإعداد للسيرفر المحاكي (اختياري) — إن لم يوجد سيقوم البوت بالتسجيل محلياً فقط
SERVER_CFG = "server_info.json"   # إذا وُجد، يقرأ host/port/allowed_tokens
SIM_SERVER_URL = None
SIM_SERVER_TOKEN = None

if os.path.exists(SERVER_CFG):
    try:
        with open(SERVER_CFG, "r") as f:
            cfg = json.load(f)
        SIM_SERVER_URL = f"http://{cfg['server_host']}:{cfg['server_port']}/simulate"
        SIM_SERVER_TOKEN = cfg.get("allowed_tokens", [None])[0]
    except Exception:
        SIM_SERVER_URL = None
        SIM_SERVER_TOKEN = None

# لوجات
BOT_LOG = "fs_sim_bot.log"
AUDIT_LOG = "fs_sim_requests.log"

logging.basicConfig(filename=BOT_LOG, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# --------- Helpers ----------
def is_owner(uid: int) -> bool:
    return uid == OWNER_ID

def valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def parse_fs(text: str):
    """
    Expected: /fs <ip> <port> <duration> <proto>
    Returns dict or None
    """
    parts = text.strip().split()
    if len(parts) != 5:
        return None
    _, ip, port_s, dur_s, proto = parts
    try:
        port = int(port_s)
        dur = int(dur_s)
    except ValueError:
        return None
    proto = proto.upper()
    if proto not in ("UDP", "TCP"):
        return None
    return {"target_ip": ip, "target_port": port, "duration": dur, "proto": proto}

def build_payload(user, ip, port, duration, proto, method="hudp", threads=5, concurrents=1):
    """Return payload matching the structure you showed (simulation values)."""
    attack_id = int(time.time() * 1000)  # ms id
    payload = {
        "attack_id": attack_id,
        "concurrents_used": concurrents,
        "duration": str(int(duration)),
        "error": False,
        "len": "1",
        "method_used": method,
        "port": str(port),
        "target": ip,
        "target_as_number": "",
        "target_city": "",
        "target_country": "",
        "target_country_code": "",
        "target_isp": "",
        "target_org": "",
        "target_region": "",
        "target_timezone": "",
        "target_zip": "",
        "threads": str(threads),
        "time_to_send": "0ms",
        "your_running_attacks": "0/4"
    }
    # include requester metadata (not sent to targets)
    payload["_requested_by"] = {"id": user.id, "username": user.username}
    return payload

def audit_log(entry: dict):
    try:
        with open(AUDIT_LOG, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        logging.exception("failed to write audit log")

# --------- Telegram handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("غير مصرح لك.")
        return
    msg = (
        "بوت محاكاة /fs جاهز.\n"
        "استخدم: /fs <IP> <PORT> <DURATION> <UDP|TCP>\n"
        f"البورتات المسموحة: {sorted(ALLOWED_PORTS)}\n"
        + (f"سيرفر المحاكاة: {SIM_SERVER_URL}" if SIM_SERVER_URL else "لا يوجد سيرفر محاكاة مكوّن؛ سيُسجَّل محليًا فقط.")
    )
    await update.message.reply_text(msg)

async def fs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("غير مصرح لك.")
        return

    raw = update.message.text or ""
    parsed = parse_fs(raw)
    if not parsed:
        await update.message.reply_text("صيغة غير صحيحة. استخدم: /fs <IP> <PORT> <DURATION> <UDP|TCP>")
        return

    ip = parsed["target_ip"]; port = parsed["target_port"]; dur = parsed["duration"]; proto = parsed["proto"]

    # validate
    if not valid_ip(ip):
        await update.message.reply_text("عنوان IP غير صالح.")
        return
    if port not in ALLOWED_PORTS:
        await update.message.reply_text(f"البورت غير مسموح. المسموح: {sorted(ALLOWED_PORTS)}")
        return

    # build payload
    payload = build_payload(user, ip, port, dur, proto, method=proto.lower() if proto else "hudp")
    entry = {"timestamp": int(time.time()), "payload": payload, "raw_cmd": raw}
    audit_log(entry)
    logging.info("Sim request by %s (%s): %s", user.username, user.id, raw)

    # send to simulation server if configured
    if SIM_SERVER_URL:
        headers = {"Content-Type": "application/json"}
        if SIM_SERVER_TOKEN:
            headers["X-Sim-Token"] = SIM_SERVER_TOKEN
        try:
            resp = requests.post(SIM_SERVER_URL, json={"cmd": "fs_simulate", "params": payload}, headers=headers, timeout=15)
            try:
                j = resp.json()
                message = j.get("message", f"Status {resp.status_code}")
            except Exception:
                message = resp.text[:1000]
            await update.message.reply_text(f"تم إرسال المحاكاة إلى السيرفر المحاكي. استجابة السيرفر: {message}")
            # update audit with server response
            entry["server_resp"] = {"status": resp.status_code, "text": message}
            audit_log(entry)
            return
        except Exception as e:
            logging.exception("failed to POST to sim server")
            entry["server_error"] = str(e)
            audit_log(entry)
            await update.message.reply_text(f"حدث خطأ عند الاتصال بسيرفر المحاكاة: {e}\nالسجّل تم إنشاؤه محليًا.")
            return

    # إذا لا يوجد سيرفر محاكاة، نعيد ملخّص المحاكاة للمستخدم
    summary = (
        f"محاكاة مُسجَّلة محليًا ✅\n"
        f"target: {ip}\nport: {port}\nduration: {dur}s\nproto: {proto}\nattack_id: {payload['attack_id']}"
    )
    await update.message.reply_text(summary)

async def get_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("غير مصرح لك.")
        return
    if not os.path.exists(AUDIT_LOG):
        await update.message.reply_text("لا سجلات بعد.")
        return
    await update.message.reply_document(open(AUDIT_LOG, "rb"))

# --------- main ----------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fs", fs_handler))
    app.add_handler(CommandHandler("logs", get_logs))
    print("fs_sim_bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()