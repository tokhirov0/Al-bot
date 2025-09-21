import os
import json
import logging
from flask import Flask, request
from telebot import TeleBot, types
from dotenv import load_dotenv

# ------------------ LOGGING ------------------
logging.basicConfig(level=logging.INFO)

# ------------------ ENV ----------------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ------------------ FILE HELPERS --------------
CHANNELS_FILE = "channels.json"
USERS_FILE = "users.json"

def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f)
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def get_channels():
    return load_json(CHANNELS_FILE, [])

def add_channel(channel):
    channels = get_channels()
    if channel not in channels:
        channels.append(channel)
        save_json(CHANNELS_FILE, channels)

def remove_channel(channel):
    channels = get_channels()
    if channel in channels:
        channels.remove(channel)
        save_json(CHANNELS_FILE, channels)

def get_users():
    return load_json(USERS_FILE, [])

def add_user(user_id):
    users = get_users()
    if user_id not in users:
        users.append(user_id)
        save_json(USERS_FILE, users)

# ------------------ CHECK SUB -----------------
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
        except Exception:
            return False
    return True

def sub_buttons():
    kb = types.InlineKeyboardMarkup()
    for ch in get_channels():
        kb.add(types.InlineKeyboardButton(f"🔗 {ch}", url=f"https://t.me/{ch[1:]}"))
    kb.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub"))
    return kb

# ------------------ HANDLERS ------------------
@bot.message_handler(commands=["start"])
def start_cmd(msg):
    user_id = msg.from_user.id
    add_user(user_id)
    if not check_subscription(user_id):
        bot.send_message(user_id, "❌ Botdan foydalanish uchun quyidagi kanallarga obuna bo‘ling:", reply_markup=sub_buttons())
        return
    bot.send_message(user_id, "🤖 Salom! Men AL-botman. Menga yozishingiz yoki guruhlarda ishlatishingiz mumkin.")

# Guruhlarda gaplashishi
@bot.message_handler(func=lambda m: True, content_types=["text"])
def chat_handler(msg):
    if msg.chat.type in ["group", "supergroup"]:
        bot.reply_to(msg, f"👋 Salom {msg.from_user.first_name}!")
    else:
        if not check_subscription(msg.from_user.id):
            bot.send_message(msg.chat.id, "❌ Iltimos, oldin obuna bo‘ling:", reply_markup=sub_buttons())
            return
        bot.send_message(msg.chat.id, "🤖 Men siz bilan gaplashishga tayyorman!")

# ------------------ CALLBACK ------------------
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub(call):
    if check_subscription(call.from_user.id):
        bot.send_message(call.from_user.id, "✅ Obuna tasdiqlandi! Endi foydalanishingiz mumkin.")
    else:
        bot.send_message(call.from_user.id, "❌ Hali ham obuna bo‘lmadingiz.", reply_markup=sub_buttons())

# ------------------ ADMIN PANEL ----------------
def admin_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Kanal qo‘shish", "➖ Kanal o‘chirish")
    kb.add("📋 Kanallar ro‘yxati")
    kb.add("👥 Statistika", "📢 Hammaga xabar")
    return kb

@bot.message_handler(commands=["admin"])
def admin_cmd(msg):
    if msg.from_user.id == ADMIN_ID:
        bot.send_message(msg.chat.id, "🔐 Admin panel:", reply_markup=admin_keyboard())

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID)
def admin_panel(msg):
    text = msg.text.strip()

    if text == "📋 Kanallar ro‘yxati":
        ch = get_channels()
        if ch:
            bot.send_message(msg.chat.id, "📋 Kanallar:\n" + "\n".join(ch))
        else:
            bot.send_message(msg.chat.id, "📋 Hozircha kanal qo‘shilmagan.")

    elif text == "➕ Kanal qo‘shish":
        bot.send_message(msg.chat.id, "➕ Kanal username kiriting (@ bilan):")
        bot.register_next_step_handler(msg, add_channel_step)

    elif text == "➖ Kanal o‘chirish":
        bot.send_message(msg.chat.id, "➖ O‘chirish uchun kanal username kiriting:")
        bot.register_next_step_handler(msg, remove_channel_step)

    elif text == "👥 Statistika":
        users = get_users()
        bot.send_message(msg.chat.id, f"👥 Foydalanuvchilar soni: {len(users)}")

    elif text == "📢 Hammaga xabar":
        bot.send_message(msg.chat.id, "📢 Yuboriladigan xabar matnini kiriting:")
        bot.register_next_step_handler(msg, broadcast_step)

def add_channel_step(msg):
    add_channel(msg.text.strip())
    bot.send_message(msg.chat.id, f"✅ {msg.text.strip()} qo‘shildi.")

def remove_channel_step(msg):
    remove_channel(msg.text.strip())
    bot.send_message(msg.chat.id, f"❌ {msg.text.strip()} o‘chirildi.")

def broadcast_step(msg):
    text = msg.text
    users = get_users()
    count = 0
    for uid in users:
        try:
            bot.send_message(uid, text)
            count += 1
        except:
            pass
    bot.send_message(msg.chat.id, f"📢 Xabar {count} ta foydalanuvchiga yuborildi.")

# ------------------ FLASK ---------------------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = request.stream.read().decode("utf-8")
    bot.process_new_updates([types.Update.de_json(update)])
    return "OK", 200

@app.route("/")
def index():
    return "AL-Bot ishlayapti!", 200

# ------------------ START ---------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
