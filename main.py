import os
import logging
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest
from supabase import create_client, Client
from dotenv import load_dotenv

# .env फाइल से वेरिएबल्स लोड करें (लोकल टेस्टिंग के लिए)
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

# Supabase क्लाइंट बनाएं
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- कॉन्फ़िगरेशन को प्रोसेस करें ---
try:
    ADMIN_IDS = [int(admin_id) for admin_id in ADMIN_IDS_STR.split(',')]
    import json
    FORCE_SUB_CHANNELS = json.loads(FORCE_SUB_CHANNELS_STR)
except (ValueError, json.JSONDecodeError) as e:
    logger.critical(f"Error parsing environment variables: {e}")
    ADMIN_IDS = []
    FORCE_SUB_CHANNELS = []

DELETE_DELAY = 900  # 15 मिनट

# --- Keep-Alive सर्वर ---
app = Flask('')
@app.route('/')
def home(): return "Bot is alive and running!"
def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# --- हेल्पर फंक्शन्स ---
async def is_user_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not FORCE_SUB_CHANNELS: return True
    for channel in FORCE_SUB_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel["chat_id"], user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']: return False
        except BadRequest: return False
    return True

async def send_force_subscribe_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_key = context.user_data.get('file_key')
    if not file_key: return # अगर file_key नहीं है तो कुछ न करें

    # --- यहाँ बटन का नया लेआउट बनाया गया है ---
    join_buttons = [
        InlineKeyboardButton(ch["name"], url=ch["invite_link"]) for ch in FORCE_SUB_CHANNELS
    ]
    
    keyboard = [
        join_buttons,  # पहली पंक्ति में "Join 1" और "Join 2"
        [InlineKeyboardButton("✅ Joined", callback_data=f"check_{file_key}")] # दूसरी पंक्ति में "Joined"
    ]
    
    await update.message.reply_text(
        "Please join all required channels to get the file.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def auto_delete_messages(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id, message_ids, file_key = job.chat_id, job.data['message_ids'], job.data['file_key']
    try:
        for msg_id in message_ids:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        keyboard = [[InlineKeyboardButton("♻️ Click Here", callback_data=f"resend_{file_key}"), InlineKeyboardButton("❌ Close ❌", callback_data="close_msg")]]
        text = "Pʀᴇᴠɪᴏᴜs Mᴇssᴀɢᴇ ᴡᴀs Dᴇʟᴇᴛᴇᴅ 🗑\nIғ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ɢᴇᴛ ᴛʜᴇ ғɪʟᴇs ᴀɢᴀɪɴ, ᴛʜᴇɴ ᴄʟɪᴄᴋ: [♻️ Cʟɪᴄᴋ Hᴇʀᴇ] ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴇʟsᴇ ᴄʟᴏsᴇ ᴛʜɪs ᴍᴇssᴀɢᴇ."
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Error in auto_delete_messages: {e}")

async def send_file_from_db(user_id: int, file_key: str, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = supabase.table('files').select('*').eq('file_key', file_key).single().execute()
        file_info = response.data
    except Exception as e:
        logger.error(f"DB error fetching {file_key}: {e}")
        await context.bot.send_message(chat_id=user_id, text="Sorry, could not find file info.")
        return

    if not file_info:
        await context.bot.send_message(chat_id=user_id, text="Sorry, file does not exist.")
        return
    
    file_type = file_info.get("file_type", "video")
    
    if file_type == 'series':
        await context.bot.send_message(chat_id=user_id, text=f"Sending all episodes... Please wait.")
        for episode_key in file_info.get("series_keys", []):
            await asyncio.sleep(2)
            await send_file_from_db(user_id, episode_key, context)
        await context.bot.send_message(chat_id=user_id, text="✅ All episodes sent!")
        return

    caption, file_id = file_info.get("caption", ""), file_info.get("file_id")
    
    try:
        if file_type == 'video':
            message_to_delete = await context.bot.send_video(chat_id=user_id, video=file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif file_type == 'document':
            message_to_delete = await context.bot.send_document(chat_id=user_id, document=file_id, caption=caption, parse_mode=ParseMode.HTML)
        else:
            message_to_delete = await context.bot.send_video(chat_id=user_id, video=file_id, caption=caption, parse_mode=ParseMode.HTML)

        warning_text = "⚠️ Dᴜᴇ ᴛᴏ Cᴏᴘʏʀɪɢʜᴛ ɪssᴜᴇs....\nYᴏᴜʀ ғɪʟᴇs ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ᴡɪᴛʜɪɴ 15 Mɪɴᴜᴛᴇs. Sᴏ ᴘʟᴇᴀsᴇ ᴅᴏᴡɴʟᴏᴀᴅ ᴏʀ ғᴏʀᴡᴀʀᴅ ᴛʜᴇᴍ."
        warning_message = await context.bot.send_message(chat_id=user_id, text=warning_text)
        
        context.job_queue.run_once(
            auto_delete_messages, 
            DELETE_DELAY, 
            data={'message_ids': [message_to_delete.message_id, warning_message.message_id], 'file_key': file_key}, 
            chat_id=user_id
        )
    except Exception as e:
        logger.error(f"Error sending file {file_key}: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if context.args:
        file_key = context.args[0]
        context.user_data['file_key'] = file_key
        
        try:
            response = supabase.table('users').select('user_id').eq('user_id', user.id).execute()
            if not response.data:
                supabase.table('users').insert({'user_id': user.id}).execute()
                logger.info(f"New user {user.id} added.")
        except Exception as e:
            logger.error(f"DB error on start for {user.id}: {e}")

        if await is_user_member(user.id, context):
            await send_file_from_db(user.id, file_key, context)
        else:
            await send_force_subscribe_message(update, context)
    else:
        await update.message.reply_text("Welcome! Please use a link from our main channel to get files.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith("check_"):
        file_key = data.split("_", 1)[1]
        
        if await is_user_member(user_id, context):
            await query.answer()
            await query.message.delete()
            await send_file_from_db(user_id, file_key, context)
        else:
            await query.answer("You haven't joined all required channels yet. Please join and try again.", show_alert=True)
            
    elif data.startswith("resend_"):
        await query.answer()
        file_key = data.split("_", 1)[1]
        await query.message.delete()
        await send_file_from_db(user_id, file_key, context)
        
    elif data == "close_msg":
        await query.message.delete()

# ... (id और get कमांड के हैंडलर वैसे ही रहेंगे) ...

def main():
    # ... (यह फंक्शन वैसा ही है)

if __name__ == '__main__':
    main()
