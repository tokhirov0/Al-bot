import os
import json
import logging
import requests
from time import sleep
from flask import Flask, request
from telebot import TeleBot, types
from dotenv import load_dotenv

# ------------ Logging ------------
logging.basicConfig(level=logging.INFO)

# ------------ Env ------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
HF_API_KEY = os.getenv("HF_API_KEY")

if not BOT_TOKEN or not HF_API_KEY or not ADMIN_ID:
    logging.error("Please set BOT_TOKEN, ADMIN_ID and HF_API_KEY in environment")
    raise SystemExit("Missing environment variables")

bot = TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

CHANNELS_FILE = "channels.json"
USERS_FILE = "users.json"

# ------------ File helpers ------------
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_channels():
    return load_json(CHANNELS_FILE, [])

def save_channels(channels):
    save_json(CHANNELS_FILE, channels)

def get_users():
    return load_json(USERS_FILE, [])

def save_users(users):
    save_json(USERS_FILE, users)

def add_user(uid):
    users = get_users()
    if uid not in users:
        users.append(uid)
        save_users(users)

# ------------ Subscription check ------------
def check_subscription(user_id):
    channels = get_channels()
    if not channels:
        return True
    for ch in channels:
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status in ["member", "administrator", "creator"]:
                continue
            else:
                return False
        except Exception as e:
            logging.warning(f"check_subscription error for {ch} and {user_id}: {e}")
            return False
    return True

def sub_buttons():
    kb = types.InlineKeyboardMarkup()
    for ch in get_channels():
        url = f"https://t.me/{ch[1:]}" if ch.startswith("@") else f"https://t.me/{ch}"
        kb.add(types.InlineKeyboardButton(text=f"🔗 {ch}", url=url))
    kb.add(types.InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub"))
    return kb

# ------------ HuggingFace AI ------------
def ask_ai(prompt, max_tokens=500):
    try:
        url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
        headers = {
            "Authorization": f"Bearer {HF_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": max_tokens}
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        j = resp.json()

        if isinstance(j, list) and "generated_text" in j[0]:
            return j[0]["generated_text"]

        return "❌ AI javobini olishda muammo yuz berdi."
    except Exception as e:
        logging.exception("ask_ai error")
        return "❌ HuggingFace serverida xatolik yuz berdi."

# ------------ Keyboards ------------
def admin_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Kanal qo‘shish", "➖ Kanal o‘chirish")
    kb.add("📋 Kanallar ro‘yxati")
    kb.add("👥 Statistika", "📢 Hammaga xabar")
    kb.add("🔙 Asosiy")
    return kb

# ------------ Handlers ------------
@bot.message_handler(commands=["start"])
def start_cmd(msg):
    uid = msg.from_user.id
    add_user(uid)
    if not check_subscription(uid):
        bot.send_message(uid, "❗ Botdan foydalanish uchun avvalo kanallarga obuna bo‘ling:", reply_markup=sub_buttons())
        return
    bot.send_message(uid, "👋 Assalomu alaykum! Men siz bilan suhbat qura olaman.")

@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def cb_check_sub(call):
    uid = call.from_user.id
    if check_subscription(uid):
        bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi")
        bot.send_message(uid, "✅ Rahmat! Endi botdan foydalanishingiz mumkin.")
    else:
        bot.answer_callback_query(call.id, "❌ Hali ham barcha kanallarga obuna bo‘lmadingiz")
        bot.send_message(uid, "Iltimos, kanallarga obuna bo‘ling:", reply_markup=sub_buttons())

# ------------ Admin flow helpers ------------
def add_channel_flow(msg):
    ch = msg.text.strip()
    channels = get_channels()
    if not ch.startswith("@"):
        bot.send_message(ADMIN_ID, "❌ Kanal username @ bilan boshlanishi kerak.")
        return
    if ch in channels:
        bot.send_message(ADMIN_ID, "⚠️ Bu kanal allaqachon ro‘yxatda.")
        return
    channels.append(ch)
    save_channels(channels)
    bot.send_message(ADMIN_ID, f"✅ Kanal qo‘shildi: {ch}")

def remove_channel_flow(msg):
    ch = msg.text.strip()
    channels = get_channels()
    if ch in channels:
        channels.remove(ch)
        save_channels(channels)
        bot.send_message(ADMIN_ID, f"🗑 Kanal o‘chirildi: {ch}")
    else:
        bot.send_message(ADMIN_ID, "❌ Kanal topilmadi.")

def broadcast_flow(msg):
    text = msg.text
    users = get_users()
    sent = 0
    for uid in users:
        try:
            bot.send_message(uid, f"📢 Xabar:\n\n{text}")
            sent += 1
            sleep(0.03)
        except Exception as e:
            logging.warning(f"Broadcast fail to {uid}: {e}")
    bot.send_message(ADMIN_ID, f"📢 Broadcast tugadi. Yuborildi: {sent} ta foydalanuvchiga.")

# ------------ Admin commands ------------
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID)
def admin_panel(m):
    text = m.text.strip() if m.text else ""
    if text == "/admin":
        bot.send_message(ADMIN_ID, "🔐 Admin panel:", reply_markup=admin_keyboard())
        return

    if text == "➕ Kanal qo‘shish":
        msg = bot.send_message(ADMIN_ID, "➕ Kanal username kiriting (@ bilan):", reply_markup=types.ForceReply(selective=False))
        bot.register_next_step_handler(msg, add_channel_flow)
        return

    if text == "➖ Kanal o‘chirish":
        msg = bot.send_message(ADMIN_ID, "➖ O‘chiriladigan kanal username kiriting:", reply_markup=types.ForceReply(selective=False))
        bot.register_next_step_handler(msg, remove_channel_flow)
        return

    if text == "📋 Kanallar ro‘yxati":
        channels = get_channels()
        bot.send_message(ADMIN_ID, "📋 Kanallar:\n" + ("\n".join(channels) if channels else "hech biri"))
        return

    if text == "👥 Statistika":
        users = get_users()
        bot.send_message(ADMIN_ID, f"👥 Foydalanuvchilar soni: {len(users)}")
        return

    if text == "📢 Hammaga xabar":
        msg = bot.send_message(ADMIN_ID, "📢 Hammaga yuboriladigan xabar matnini kiriting:", reply_markup=types.ForceReply(selective=False))
        bot.register_next_step_handler(msg, broadcast_flow)
        return

    if text == "🔙 Asosiy":
        bot.send_message(ADMIN_ID, "🔙 Asosiy menyu", reply_markup=types.ReplyKeyboardRemove())
        return

# ------------ Message handler: AI reply ------------
@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_message(m):
    if m.from_user.is_bot:
        return

    uid = m.chat.id
    add_user(uid)

    if not check_subscription(m.from_user.id):
        bot.send_message(m.chat.id, "❗ Botdan foydalanish uchun avvalo kanallarga obuna bo‘ling:", reply_markup=sub_buttons())
        return

    try:
        bot.send_chat_action(uid, "typing")
    except:
        pass

    prompt = m.text or ""
    reply = ask_ai(prompt)
    try:
        if m.chat.type in ("group", "supergroup"):
            bot.reply_to(m, reply)
        else:
            bot.send_message(uid, reply)
    except Exception as e:
        logging.exception("Send reply failed")

# ------------ Flask webhook endpoint ------------
@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        update = request.get_json(force=True)
        if update:
            bot.process_new_updates([types.Update.de_json(update)])
        return "OK", 200
    except Exception as e:
        logging.exception("Webhook processing error")
        return "ERR", 500

@app.route("/", methods=["GET"])
def index():
    return "AL-Bot is running ✅", 200

# ------------ Run ------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
