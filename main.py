import os
import logging
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode
from telegram.error import BadRequest
from supabase import create_client, Client
from dotenv import load_dotenv

# .env फाइल लोड करें
load_dotenv()

# === बेसिक सेटअप ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- एनवायरनमेंट वेरिएबल्स से सीक्रेट्स लें ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "")
FORCE_SUB_CHANNELS_STR = os.environ.get("FORCE_SUB_CHANNELS", "[]")

# Supabase क्लाइंट
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- कॉन्फ़िगरेशन प्रोसेस करें ---
try:
    ADMIN_IDS = [int(admin_id) for admin_id in ADMIN_IDS_STR.split(',')]
    import json
    FORCE_SUB_CHANNELS = json.loads(FORCE_SUB_CHANNELS_STR)
except (ValueError, json.JSONDecodeError) as e:
    logger.critical(f"Error parsing env variables: {e}")
    ADMIN_IDS, FORCE_SUB_CHANNELS = [], []

DELETE_DELAY = 900

# --- बॉट का एप्लीकेशन ऑब्जेक्ट ---
# इसे हम ग्लोबली डिफाइन करेंगे
application = Application.builder().token(TOKEN).build()

# ... (सभी हेल्पर फंक्शन्स और कमांड हैंडलर्स यहाँ आएंगे) ...
# (यह फंक्शन्स पिछले कोड जैसे ही हैं, इसलिए मैं उन्हें संक्षिप्त कर रहा हूँ)
async def is_user_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    # ... (सेम कोड)
async def send_force_subscribe_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (सेम कोड, नए बटन लेआउट के साथ)
async def auto_delete_messages(context: ContextTypes.DEFAULT_TYPE):
    # ... (सेम कोड)
async def send_file_from_db(user_id: int, file_key: str, context: ContextTypes.DEFAULT_TYPE):
    # ... (सेम कोड)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (सेम कोड)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (सेम कोड)
async def get_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (सेम कोड)
async def get_forward_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (सेम कोड)

# --- हैंडलर्स को रजिस्टर करें ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(CommandHandler("id", get_id_handler))
application.add_handler(CommandHandler("get", get_forward_id_handler))

# --- Flask वेब सर्वर ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is alive and running!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- मुख्य फंक्शन ---
def main():
    # Flask को एक अलग थ्रेड में चलाएं
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    logger.info("Keep-alive server started.")
    logger.info("Bot is starting polling...")
    
    # अब बॉट को पोलिंग मोड में चलाएं
    application.run_polling()

if __name__ == '__main__':
    if not all([TOKEN, SUPABASE_URL, SUPABASE_KEY]):
        logger.critical("Missing critical environment variables!")
    else:
        main()
