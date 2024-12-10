import asyncio
import logging
import random
import json
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
token = os.getenv('BOT_TOKEN')
print(f"Debug - Token read from .env: {token}")
bot = Bot(token=token)
dp = Dispatcher()

# Constants
WORDLISTS_DIR = "wordlists"
DEFAULT_WORDLIST = "swear"

def get_available_wordlists():
    """Get list of available word list files"""
    try:
        files = os.listdir(WORDLISTS_DIR)
        return [f.replace('.txt', '') for f in files if f.endswith('.txt')]
    except Exception as e:
        logging.error(f"Error reading wordlists directory: {e}")
        return []

def load_words(list_name=DEFAULT_WORDLIST):
    """Load words from specified word list file"""
    try:
        file_path = os.path.join(WORDLISTS_DIR, f"{list_name}.txt")
        with open(file_path, 'r', encoding='utf-8') as file:
            words = [word.strip() for word in file.readlines() if word.strip()]
            if not words:
                raise ValueError("Word list is empty")
            return words
    except FileNotFoundError:
        logging.error(f"Word list '{list_name}' not found!")
        return load_words(DEFAULT_WORDLIST) if list_name != DEFAULT_WORDLIST else ["default_word"]
    except Exception as e:
        logging.error(f"Error reading word list '{list_name}': {e}")
        return load_words(DEFAULT_WORDLIST) if list_name != DEFAULT_WORDLIST else ["default_word"]

def load_users():
    """Load users from users.json file"""
    try:
        with open('users.json', 'r') as file:
            data = json.load(file)
            users = {}
            user_lists = {}
            
            # Convert stored user data
            for user_id, last_word_time in data.get('active_users', {}).items():
                users[int(user_id)] = datetime.fromisoformat(last_word_time) if last_word_time else None
            
            # Load user list preferences
            for user_id, lists in data.get('user_lists', {}).items():
                user_lists[int(user_id)] = lists

            return users, user_lists
    except FileNotFoundError:
        logging.warning("users.json not found, creating new file")
        save_users({}, {})
        return {}, {}
    except Exception as e:
        logging.error(f"Error loading users.json: {e}")
        return {}, {}

def save_users(users, user_lists):
    """Save users to users.json file"""
    try:
        serializable_users = {
            str(user_id): user_time.isoformat() if user_time else None
            for user_id, user_time in users.items()
        }
        
        serializable_lists = {
            str(user_id): lists
            for user_id, lists in user_lists.items()
        }
        
        with open('users.json', 'w') as file:
            json.dump({
                'active_users': serializable_users,
                'user_lists': serializable_lists,
                'version': 2
            }, file, indent=4)
        return True
    except Exception as e:
        logging.error(f"Error saving users.json: {e}")
        return False

# Store active users with their last word times and list preferences
active_users, user_lists = load_users()

# Load default word list
current_list_name = DEFAULT_WORDLIST
WORD_LIST = load_words(current_list_name)

async def should_send_word(user_id):
    """Check if it's time to send a new word to the user"""
    last_time = active_users.get(user_id)
    if last_time is None:
        return True
    
    now = datetime.now()
    return (now - last_time) >= timedelta(hours=24)

async def send_word_to_user(user_id, force=False):
    """Send random words from user's selected lists"""
    if user_id not in active_users:
        active_users[user_id] = None
        user_lists.setdefault(user_id, [DEFAULT_WORDLIST])
        save_users(active_users, user_lists)

    if not force and not await should_send_word(user_id):
        time_diff = timedelta(hours=24) - (datetime.now() - active_users[user_id])
        hours, remainder = divmod(time_diff.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        await bot.send_message(
            user_id,
            f"⏳ Please wait {hours}h {minutes}m for your next words.\n"
            "Or use /skip to get new words immediately!"
        )
        return True

    selected_lists = user_lists.get(user_id, [DEFAULT_WORDLIST])
    current_time = datetime.now()
    success = False
    
    for list_name in selected_lists:
        try:
            word_list = load_words(list_name)
            word = random.choice(word_list)
            
            await bot.send_message(
                user_id,
                f"🎯 Your word from '{list_name}' ({current_time.strftime('%H:%M:%S')}):\n\n"
                f"✨ *{word}*",
                parse_mode="Markdown"
            )
            success = True
        except Exception as e:
            logging.error(f"Failed to send word from list '{list_name}' to {user_id}: {e}")
    
    if success:
        active_users[user_id] = current_time
        save_users(active_users, user_lists)
        
    return success

async def send_daily_word():
    """Send a random word to all users who haven't received one in 24 hours"""
    if not active_users:
        return
    
    for user_id in list(active_users.keys()):
        if await should_send_word(user_id):
            success = await send_word_to_user(user_id)
            if not success:
                del active_users[user_id]
                save_users(active_users, user_lists)

@dp.message(Command('skip'))
async def skip_word(message: types.Message):
    """Skip current word and get a new one"""
    user_id = message.from_user.id
    if user_id not in active_users and user_id not in user_lists:
        await message.reply("You're not subscribed! Use /start first.")
        return
    
    await send_word_to_user(user_id, force=True)

@dp.message(Command('start'))
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    active_users[user_id] = None
    user_lists[user_id] = [DEFAULT_WORDLIST]
    save_users(active_users, user_lists)
    
    await message.reply(
        "Hello! I'm your Daily Word Bot. 📚\n"
        "You'll receive words from your selected lists every 24 hours.\n"
        "Available commands:\n"
        "/stop - Unsubscribe from daily words\n"
        "/skip - Get new words immediately\n"
        "/lists - Show your active lists\n"
        "/addlist <name> - Add a list\n"
        "/remlist <name> - Remove a list\n"
        "/wordlists - Show all available lists\n"
        "/list - Show words in current list"
    )
    
    await send_word_to_user(user_id)

@dp.message(Command('stop'))
async def stop_notifications(message: types.Message):
    user_id = message.from_user.id
    if user_id in active_users:
        del active_users[user_id]
        save_users(active_users, user_lists)
    await message.reply("You've been unsubscribed from daily words. Use /start to subscribe again.")

@dp.message(Command('wordlists'))
async def list_wordlists(message: types.Message):
    """Show available word lists"""
    available_lists = get_available_wordlists()
    if not available_lists:
        await message.reply("No word lists found!")
        return
    
    lists_text = "\n".join(
        f"• {lst}" + (" (current)" if lst == current_list_name else "")
        for lst in sorted(available_lists)
    )
    await message.reply(
        f"📚 Available word lists:\n\n{lists_text}\n\n"
        "Use /setlist <name> to switch lists"
    )

@dp.message(Command('lists'))
async def show_my_lists(message: types.Message):
    """Show user's active word lists"""
    user_id = message.from_user.id
    if user_id not in active_users and user_id not in user_lists:
        await message.reply("You're not subscribed! Use /start first.")
        return

    selected_lists = user_lists.get(user_id, [DEFAULT_WORDLIST])
    available_lists = get_available_wordlists()
    
    active_text = "\n".join(f"• {lst}" for lst in sorted(selected_lists))
    available_text = "\n".join(f"• {lst}" for lst in sorted(available_lists) if lst not in selected_lists)
    
    response = f"📚 Your active lists:\n{active_text}\n"
    if available_text:
        response += f"\nAvailable lists:\n{available_text}"
    
    await message.reply(
        f"{response}\n\n"
        "Commands:\n"
        "/addlist <name> - Add a list\n"
        "/remlist <name> - Remove a list"
    )

@dp.message(Command('addlist'))
async def add_list(message: types.Message, command: CommandObject):
    """Add a word list to user's active lists"""
    user_id = message.from_user.id
    if user_id not in active_users and user_id not in user_lists:
        await message.reply("You're not subscribed! Use /start first.")
        return
    
    if not command.args:
        await message.reply("Please provide a list name.\nUsage: /addlist <name>")
        return
    
    list_name = command.args.strip().lower()
    available_lists = get_available_wordlists()
    
    if list_name not in available_lists:
        lists = ", ".join(available_lists)
        await message.reply(
            f"Word list '{list_name}' not found!\n"
            f"Available lists: {lists}"
        )
        return
    
    user_lists.setdefault(user_id, [DEFAULT_WORDLIST])
    if list_name in user_lists[user_id]:
        await message.reply(f"List '{list_name}' is already active!")
        return
    
    user_lists[user_id].append(list_name)
    save_users(active_users, user_lists)
    await message.reply(f"Added '{list_name}' to your active lists!")

@dp.message(Command('remlist'))
async def remove_list(message: types.Message, command: CommandObject):
    """Remove a word list from user's active lists"""
    user_id = message.from_user.id
    if user_id not in active_users and user_id not in user_lists:
        await message.reply("You're not subscribed! Use /start first.")
        return
    
    if not command.args:
        await message.reply("Please provide a list name.\nUsage: /remlist <name>")
        return
    
    list_name = command.args.strip().lower()
    
    if user_id not in user_lists or list_name not in user_lists[user_id]:
        await message.reply(f"List '{list_name}' is not in your active lists!")
        return
    
    if len(user_lists[user_id]) == 1:
        await message.reply("Cannot remove your last active list!")
        return
    
    user_lists[user_id].remove(list_name)
    save_users(active_users, user_lists)
    await message.reply(f"Removed '{list_name}' from your active lists!")

@dp.message()
async def handle_any_message(message: types.Message):
    """Handle any unrecognized message or command"""
    user_id = message.from_user.id
    if user_id not in active_users and user_id not in user_lists:
        await message.reply("You're not subscribed! Use /start first.")
        return
    
    await message.reply(
        "Available commands:\n"
        "/stop - Unsubscribe from daily words\n"
        "/skip - Get new words immediately\n"
        "/lists - Show your active lists\n"
        "/addlist <name> - Add a list\n"
        "/remlist <name> - Remove a list\n"
        "/wordlists - Show all available lists\n"
        "/list - Show words in current list"
    )

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