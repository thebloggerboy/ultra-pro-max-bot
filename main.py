import os
import logging
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from supabase import create_client, Client
from dotenv import load_dotenv

# .env फाइल से वेरिएबल्स लोड करें (लोकल टेस्टिंग के लिए)
load_dotenv()

# === बेसिक सेटअप ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Supabase और Telegram टोकन को एनवायरनमेंट से लें ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Supabase क्लाइंट बनाएं
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- एडमिन ID ---
ADMIN_IDS = [6056915535] # <-- अपनी एडमिन ID यहाँ डालें

# --- Keep-Alive सर्वर (Render + UptimeRobot के लिए) ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is alive and running!"
def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# --- बॉट के फंक्शन्स ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    try:
        # चेक करें कि यूजर पहले से डेटाबेस में है या नहीं
        response = supabase.table('users').select('user_id').eq('user_id', user_id).execute()
        
        # अगर यूजर नहीं है, तो उसे डेटाबेस में जोड़ें
        if not response.data:
            supabase.table('users').insert({'user_id': user_id, 'language': 'en'}).execute()
            logger.info(f"New user {user_id} added to the database.")
            await update.message.reply_text(f"Welcome, {user.first_name}! I've registered you.")
        else:
            logger.info(f"User {user_id} is already registered.")
            await update.message.reply_text(f"Welcome back, {user.first_name}!")

    except Exception as e:
        logger.error(f"Database error on start for user {user_id}: {e}")
        await update.message.reply_text("Sorry, there was an error connecting to the database.")

async def id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    msg = update.message.reply_to_message
    if not msg:
        await update.message.reply_text("Please reply to a message.")
        return
    await update.message.reply_text(f"User ID: {msg.from_user.id}\nChat ID: {msg.chat.id}")

# --- मुख्य फंक्शन ---
def main():
    if not all([TOKEN, SUPABASE_URL, SUPABASE_KEY]):
        logger.critical("Missing one or more required environment variables!")
        return

    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("id", id_handler))

    keep_alive()
    logger.info("Keep-alive server started.")
    
    logger.info("Bot is starting polling...")
    application.run_polling()

if __name__ == '__main__':
    main()
