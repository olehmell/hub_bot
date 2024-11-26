from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
FORWARD_CHAT_ID = os.getenv('FORWARD_CHAT_ID')
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')

if not BOT_TOKEN or not FORWARD_CHAT_ID:
    raise ValueError("Missing required environment variables. Please check your .env file")

# Initialize MongoDB connection
client = MongoClient(MONGO_URI)
db = client['telegram_bot']
message_mappings = db['message_mappings']

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє команду /start."""
    await update.message.reply_text("Вітаю! Напишіть або надішліть фото, і я передам його далі.")

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forwards user message to the target chat."""
    message = update.message
    
    if message.from_user.id == context.bot.id:
        return
        
    if message.chat.type != 'private':
        return

    forwarded_message = await context.bot.forward_message(
        chat_id=FORWARD_CHAT_ID,
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )

    # Store message association in MongoDB
    message_mappings.insert_one({
        "_id": forwarded_message.message_id,
        "user_chat_id": message.chat.id,
        "user_message_id": message.message_id,
    })

async def handle_replies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles replies from the forward chat."""
    message = update.message
    
    if message.chat.id != int(FORWARD_CHAT_ID):
        return
        
    if not message.reply_to_message:
        return
        
    # Get original message data from MongoDB
    original_msg_id = message.reply_to_message.message_id
    original_data = message_mappings.find_one({"_id": original_msg_id})
    
    if not original_data:
        return
        
    # Forward the reply directly to the original user
    await context.bot.copy_message(
        chat_id=original_data["user_chat_id"],
        from_chat_id=message.chat.id,
        message_id=message.message_id,
        reply_to_message_id=original_data["user_message_id"]
    )

def main():
    """Starts the bot."""
    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    
    # Handle replies from forward chat first
    app.add_handler(MessageHandler(
        filters.Chat(chat_id=int(FORWARD_CHAT_ID)) & filters.REPLY,
        handle_replies
    ))
    
    # Handle all user messages except commands
    app.add_handler(MessageHandler(
        ~filters.COMMAND,
        forward_message
    ))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()