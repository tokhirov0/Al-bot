import os
import json
import logging
import requests
from flask import Flask, request
from telebot import TeleBot, types
from dotenv import load_dotenv

# --- Logging ---
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Muhit o‘zgaruvchilari ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

bot = TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- JSON fayllar ---
USERS_FILE = "users.json"
CHANNELS_FILE = "channels.json"

def load_json(file, default):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump(default, f)
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# --- Foydalanuvchilar ---
def get_user(chat_id):
    users = load_json(USERS_FILE, {})
    if str(chat_id) not in users:
        users[str(chat_id)] = {"messages": 0}
        save_json(USERS_FILE, users)
    return users[str(chat_id)]

def update_user(chat_id, user_data):
    users = load_json(USERS_FILE, {})
    users[str(chat_id)] = user_data
    save_json(USERS_FILE, users)

# --- Kanallar ---
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

# --- Kanal tekshiruvi ---
def check_channel_membership(chat_id):
    channels = get_channels()
    for ch in channels:
        try:
            member = bot.get_chat_member(ch, chat_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True

# --- Menyular ---
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💬 Suhbat")
    return kb

def admin_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📊 Statistika", "➕ Kanal qo‘shish", "❌ Kanal o‘chirish")
    kb.add("🔙 Orqaga")
    return kb

def force_subscribe(chat_id):
    channels = get_channels()
    if not channels:
        return False
    kb = types.InlineKeyboardMarkup()
    for ch in channels:
        kb.add(types.InlineKeyboardButton(
            text=f"🔗 {ch}",
            url=f"https://t.me/{ch[1:]}" if ch.startswith("@") else f"https://t.me/{ch}"
        ))
    kb.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_subs"))
    bot.send_message(chat_id, "👉 Botdan foydalanish uchun quyidagi kanallarga obuna bo‘ling:", reply_markup=kb)
    return True

# --- OpenRouter AI ---
def ask_ai(prompt):
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}]
        }
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        result = resp.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error(f"AI error: {e}")
        return "❌ AI serverida xatolik yuz berdi."

# --- /start ---
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    if not check_channel_membership(chat_id):
        force_subscribe(chat_id)
        return
    bot.send_message(chat_id, "👋 Assalomu alaykum! Men AL botman.\nSavollaringizni yozing.", reply_markup=main_menu())

# --- Callback tekshirish ---
@bot.callback_query_handler(func=lambda call: call.data=="check_subs")
def recheck(call):
    if check_channel_membership(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Obuna bo‘ldingiz!")
        bot.send_message(call.message.chat.id, "Botdan foydalanishingiz mumkin ✅", reply_markup=main_menu())
    else:
        bot.answer_callback_query(call.id, "❌ Hali barcha kanallarga obuna bo‘lmadingiz.")
        force_subscribe(call.message.chat.id)

# --- AI suhbat ---
@bot.message_handler(func=lambda m: m.text=="💬 Suhbat")
def chat_mode(message):
    bot.send_message(message.chat.id, "✍️ Menga savolingizni yozing.")

@bot.message_handler(func=lambda m: True)
def chat(message):
    chat_id = message.chat.id
    if chat_id == ADMIN_ID and message.text == "/admin":
        bot.send_message(chat_id, "Admin paneli:", reply_markup=admin_menu())
        return

    if not check_channel_membership(chat_id):
        force_subscribe(chat_id)
        return

    user = get_user(chat_id)
    user["messages"] += 1
    update_user(chat_id, user)

    reply = ask_ai(message.text)
    bot.reply_to(message, reply)

# --- Admin panel ---
@bot.message_handler(func=lambda m: m.chat.id==ADMIN_ID)
def admin(message):
    if message.text=="📊 Statistika":
        users = load_json(USERS_FILE, {})
        bot.send_message(message.chat.id, f"👥 Jami foydalanuvchilar: {len(users)}")
    elif message.text=="➕ Kanal qo‘shish":
        msg = bot.send_message(message.chat.id, "Kanal username kiriting (@ bilan):", reply_markup=types.ForceReply(selective=False))
        bot.register_next_step_handler(msg, lambda m: add_channel(m.text) or bot.send_message(message.chat.id, f"Kanal qo‘shildi: {m.text}"))
    elif message.text=="❌ Kanal o‘chirish":
        msg = bot.send_message(message.chat.id, "O‘chiriladigan kanal username:", reply_markup=types.ForceReply(selective=False))
        bot.register_next_step_handler(msg, lambda m: remove_channel(m.text) or bot.send_message(message.chat.id, f"Kanal o‘chirildi: {m.text}"))
    elif message.text=="🔙 Orqaga":
        bot.send_message(message.chat.id, "Asosiy menyuga qaytildi", reply_markup=main_menu())

# --- Flask webhook ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json(force=True)
    if update:
        bot.process_new_updates([types.Update.de_json(update)])
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
