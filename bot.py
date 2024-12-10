import asyncio
import logging
import random
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher()

# Store active users
active_users = set()

def load_words():
    """Load words from words.txt file"""
    try:
        with open('words.txt', 'r', encoding='utf-8') as file:
            return [word.strip() for word in file.readlines() if word.strip()]
    except FileNotFoundError:
        logging.error("words.txt file not found!")
        return ["default_word"]  # Fallback word if file not found
    except Exception as e:
        logging.error(f"Error reading words.txt: {e}")
        return ["default_word"]

# Load words from file
WORD_LIST = load_words()

async def send_daily_word():
    """Send a random word to all active users"""
    if not active_users:
        return
    
    word = random.choice(WORD_LIST)
    current_time = datetime.now().strftime("%H:%M:%S")
    
    for user_id in active_users:
        try:
            await bot.send_message(
                user_id,
                f"🎯 Your daily word ({current_time}):\n\n"
                f"✨ *{word}*",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Failed to send message to {user_id}: {e}")

# Command handler for /start
@dp.message(Command('start'))
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    active_users.add(user_id)
    
    await message.reply(
        "Hello! I'm your Daily Word Bot. 📚\n"
        "You'll receive a random word every 24 hours.\n"
        "Use /stop to unsubscribe."
    )
    
    # Send first word immediately
    await send_daily_word()

# Command handler for /stop
@dp.message(Command('stop'))
async def stop_notifications(message: types.Message):
    user_id = message.from_user.id
    active_users.discard(user_id)
    await message.reply("You've been unsubscribed from daily words. Use /start to subscribe again.")

# Command to reload words from file
@dp.message(Command('reload'))
async def reload_words(message: types.Message):
    global WORD_LIST
    WORD_LIST = load_words()
    await message.reply(f"Word list reloaded. Total words: {len(WORD_LIST)}")

# Main function to start the bot
async def main():
    # Initialize scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_word, 'interval', hours=24)
    scheduler.start()
    
    # Delete webhook before polling
    await bot.delete_webhook(drop_pending_updates=True)
    # Start polling
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main()) 