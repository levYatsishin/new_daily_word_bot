import asyncio
import logging
import random
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
token = os.getenv('BOT_TOKEN')
print(f"Debug - Token read from .env: {token}")
bot = Bot(token=token)
dp = Dispatcher()

def load_users():
    """Load users from users.json file"""
    try:
        with open('users.json', 'r') as file:
            data = json.load(file)
            return set(data.get('active_users', []))
    except FileNotFoundError:
        logging.warning("users.json not found, creating new file")
        save_users(set())
        return set()
    except Exception as e:
        logging.error(f"Error loading users.json: {e}")
        return set()

def save_users(users):
    """Save users to users.json file"""
    try:
        with open('users.json', 'w') as file:
            json.dump({'active_users': list(users)}, file, indent=4)
        return True
    except Exception as e:
        logging.error(f"Error saving users.json: {e}")
        return False

# Store active users
active_users = load_users()

def load_words():
    """Load words from words.txt file"""
    try:
        with open('words.txt', 'r', encoding='utf-8') as file:
            return [word.strip() for word in file.readlines() if word.strip()]
    except FileNotFoundError:
        logging.error("words.txt file not found!")
        return ["default_word"]
    except Exception as e:
        logging.error(f"Error reading words.txt: {e}")
        return ["default_word"]

def save_words(words):
    """Save words to words.txt file"""
    try:
        with open('words.txt', 'w', encoding='utf-8') as file:
            file.write('\n'.join(words))
        return True
    except Exception as e:
        logging.error(f"Error saving words.txt: {e}")
        return False

# Load words from file
WORD_LIST = load_words()

async def send_daily_word():
    """Send a random word to all active users"""
    if not active_users:
        return
    
    word = random.choice(WORD_LIST)
    current_time = datetime.now().strftime("%H:%M:%S")
    
    for user_id in list(active_users):  # Create a copy of the set for iteration
        try:
            await bot.send_message(
                user_id,
                f"🎯 Your daily word ({current_time}):\n\n"
                f"✨ *{word}*",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Failed to send message to {user_id}: {e}")
            # If we can't send message to user (blocked bot, etc.), remove them
            active_users.discard(user_id)
            save_users(active_users)

@dp.message(Command('start'))
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    active_users.add(user_id)
    save_users(active_users)
    
    await message.reply(
        "Hello! I'm your Daily Word Bot. 📚\n"
        "You'll receive a random word every 24 hours.\n"
        "Available commands:\n"
        "/stop - Unsubscribe from daily words\n"
        "/add <word> - Add a new word\n"
        "/remove <word> - Remove a word\n"
        "/list - Show all words\n"
        "/reload - Reload words from file"
    )
    
    # Send first word immediately
    await send_daily_word()

@dp.message(Command('stop'))
async def stop_notifications(message: types.Message):
    user_id = message.from_user.id
    active_users.discard(user_id)
    save_users(active_users)
    await message.reply("You've been unsubscribed from daily words. Use /start to subscribe again.")

@dp.message(Command('add'))
async def add_word(message: types.Message, command: CommandObject):
    if not command.args:
        await message.reply("Please provide a word to add.\nUsage: /add <word>")
        return
    
    word = command.args.strip().lower()
    if word in WORD_LIST:
        await message.reply(f"Word '{word}' is already in the list!")
        return
    
    WORD_LIST.append(word)
    if save_words(WORD_LIST):
        await message.reply(f"Word '{word}' added successfully!")
    else:
        WORD_LIST.remove(word)
        await message.reply("Failed to save the word. Please try again later.")

@dp.message(Command('remove'))
async def remove_word(message: types.Message, command: CommandObject):
    if not command.args:
        await message.reply("Please provide a word to remove.\nUsage: /remove <word>")
        return
    
    word = command.args.strip().lower()
    if word not in WORD_LIST:
        await message.reply(f"Word '{word}' is not in the list!")
        return
    
    WORD_LIST.remove(word)
    if save_words(WORD_LIST):
        await message.reply(f"Word '{word}' removed successfully!")
    else:
        WORD_LIST.append(word)
        await message.reply("Failed to remove the word. Please try again later.")

@dp.message(Command('list'))
async def list_words(message: types.Message):
    words_text = "\n".join(f"• {word}" for word in sorted(WORD_LIST))
    await message.reply(
        f"📝 Current word list ({len(WORD_LIST)} words):\n\n{words_text}",
        parse_mode="Markdown"
    )

@dp.message(Command('reload'))
async def reload_words(message: types.Message):
    global WORD_LIST
    WORD_LIST = load_words()
    await message.reply(f"Word list reloaded. Total words: {len(WORD_LIST)}")

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