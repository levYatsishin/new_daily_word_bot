import asyncio
import logging
import random
import json
import os
from datetime import datetime, timedelta
import time
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
DEFAULT_WORDLIST = ["swear", "fenia"] 
SEND_INTERVAL = timedelta(minutes=10)  # Define the interval for sending new messages

def get_available_wordlists():
    """Get list of available word list files"""
    try:
        files = os.listdir(WORDLISTS_DIR)
        return [f.replace('.txt', '') for f in files if f.endswith('.txt')]
    except Exception as e:
        logging.error(f"Error reading wordlists directory: {e}")
        return []

def load_words(list_names=DEFAULT_WORDLIST):
    """Load words from specified word list files"""
    words = []
    for list_name in list_names:
        try:
            file_path = os.path.join(WORDLISTS_DIR, f"{list_name}.txt")
            with open(file_path, 'r', encoding='utf-8') as file:
                list_words = [word.strip() for word in file if word.strip()]
                print(f"List words: {len(list_words)}")
                if not list_words:
                    raise ValueError(f"Word list '{list_name}' is empty")
                words.extend(list_words)  # Add the list of words to the total without shuffling
        except FileNotFoundError:
            logging.error(f"Word list '{list_name}' not found!")
            if list_name != DEFAULT_WORDLIST:
                continue  # Skip if it's not the default list
        except Exception as e:
            logging.error(f"Error reading word list '{list_name}': {e}")
    
    return words if words else ["default_word"]  # Return a default word if no words found

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

            # Debug print
            print(f"Loaded users: {users}")
            print(f"Loaded user_lists: {user_lists}")
            
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
        # Convert user IDs to strings for JSON serialization
        serializable_users = {
            str(user_id): user_time.isoformat() if user_time else None
            for user_id, user_time in users.items()
        }
        
        # Convert user IDs to strings for user lists
        serializable_lists = {
            str(user_id): lists
            for user_id, lists in user_lists.items()
        }
        
        data = {
            'active_users': serializable_users,
            'user_lists': serializable_lists,
            'version': 2
        }
        
        # Debug print before saving
        print(f"About to save data: {data}")
        
        with open('users.json', 'w') as file:
            json.dump(data, file, indent=4)
            
        # Verify the save
        with open('users.json', 'r') as file:
            saved_data = json.load(file)
            print(f"Verified saved data: {saved_data}")
            
        return True
    except Exception as e:
        logging.error(f"Error saving users.json: {e}")
        return False

# Store active users with their last word times and list preferences
def load_active_users_and_lists():
    active_users, user_lists = load_users()
    return active_users, user_lists

active_users, user_lists = load_active_users_and_lists()

# Load default word list
current_list_name = DEFAULT_WORDLIST
WORD_LIST = load_words(current_list_name)

async def should_send_word(user_id):
    """Check if it's time to send a new word to the user"""
    last_time = active_users.get(user_id)
    if last_time is None:
        return True
    
    now = datetime.now()
    print(f"Debug - now: {now}, last_time: {last_time}, SEND_INTERVAL: {SEND_INTERVAL}")
    print(f"{(now - last_time) >= SEND_INTERVAL}")
    return (now - last_time) >= SEND_INTERVAL

async def send_word_to_user(user_id, force=False):
    """Send random words from user's selected lists"""
    active_users, user_lists = load_active_users_and_lists()
    print(f"Debug - send_word_to_user called with user_id: {user_id}, force: {force}")
    if user_id not in active_users:
        active_users[user_id] = None
        user_lists.setdefault(user_id, DEFAULT_WORDLIST)
        save_users(active_users, user_lists)

    selected_lists = user_lists.get(user_id, DEFAULT_WORDLIST)
    current_time = datetime.now()
    success = False
    
    for list_name in selected_lists:
        try:
            word_list = load_words([list_name])
            word = random.sample(word_list, 1)[0]
            
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
        print(f"{active_users[user_id]}")
        save_users(active_users, user_lists)
        
    return success

async def send_daily_word():
    """Send a random word to all users who haven't received one in 24 hours"""
    active_users, user_lists = load_active_users_and_lists()
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
    active_users, user_lists = load_active_users_and_lists()
    user_id = message.from_user.id
    if user_id not in active_users and user_id not in user_lists:
        await message.reply("You're not subscribed! Use /start first.")
        return
    
    await send_word_to_user(user_id, force=True)

@dp.message(Command('start'))
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    active_users, user_lists = load_active_users_and_lists()
    
    print(f"Start command received. Current user_lists: {user_lists}")  # Debug print
    print(f"User {user_id} exists in lists: {user_id in user_lists}")  # Debug print
    
    available_lists = get_available_wordlists()
    available_lists_text = "\n".join(f"• {lst}" for lst in sorted(available_lists))
    
    await message.reply(
        "Hello! I'm your Daily Word Bot. 📚\n"
        "You'll receive words from your selected lists every 24 hours.\n"
        "Available commands:\n"
        "/stop - Unsubscribe from daily words\n"
        "/skip - Get new words immediately\n"
        "/lists - Show your active lists\n"
        "/addlist <name> - Add a list\n"
        "/remlist <name> - Remove a list\n"
        "/list - Show words in current list\n\n"
        "Available lists\n"
        f"{available_lists_text}\n"
        "Use /addlist <list_name> to add a list."
        "Use /remlist <list_name> to remove a list."
    )

    # Only initialize if user doesn't exist in either dictionary
    if user_id not in user_lists:
        print(f"New user {user_id}, initializing with default list")  # Debug print
        user_lists[user_id] = DEFAULT_WORDLIST
        active_users[user_id] = None
        save_users(active_users, user_lists)

        await send_word_to_user(user_id)

    else:
        print(f"Debug - active_users[user_id]: {active_users[user_id]}")
        time_diff = SEND_INTERVAL - (datetime.now() - active_users[user_id])
        hours, remainder = divmod(time_diff.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours == 0 and minutes == 0 and seconds == 0:
            await message.reply(
                "⏳ Please wait about 5 minutes for your next words.\n"
                "Or use /skip to get new words immediately!"
            )
        else:
            await message.reply(
                f"⏳ Please wait {hours}h {minutes}m {seconds}s for your next words.\n"
                "Or use /skip to get new words immediately!"
            )


@dp.message(Command('stop'))
async def stop_notifications(message: types.Message):
    user_id = message.from_user.id
    active_users, user_lists = load_active_users_and_lists()
    if user_id in active_users:
        del active_users[user_id]
        save_users(active_users, user_lists)
    await message.reply("You've been unsubscribed from daily words. Use /start to subscribe again.")


@dp.message(Command('lists'))
async def show_my_lists(message: types.Message):
    """Show user's active word lists"""
    active_users, user_lists = load_active_users_and_lists()
    user_id = message.from_user.id
    if user_id not in active_users and user_id not in user_lists:
        await message.reply("You're not subscribed! Use /start first.")
        return

    selected_lists = user_lists.get(user_id, DEFAULT_WORDLIST)
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
    active_users, user_lists = load_active_users_and_lists()
    user_id = message.from_user.id
    available_lists = get_available_wordlists()
    
    # If no list name provided, show available lists
    if not command.args:
        user_active_lists = user_lists.get(user_id, DEFAULT_WORDLIST)
        available_text = "\n".join(
            f"• {lst}" + (" (active)" if lst in user_active_lists else "")
            for lst in sorted(available_lists)
        )
        await message.reply(
            "Please provide a list name.\n"
            f"Available lists:\n{available_text}\n\n"
            "Usage: /addlist <name>"
        )
        return
    
    list_name = command.args.strip().lower()
    print(f"Adding list: {list_name}")  # Debug print
    print(f"Available lists: {available_lists}")  # Debug print
    
    # Rest of the function remains the same...
    if list_name not in available_lists:
        await message.reply(f"List '{list_name}' not found! Available lists: {', '.join(available_lists)}")
        return
    
    if user_id not in user_lists:
        user_lists[user_id] = DEFAULT_WORDLIST
    
    if list_name not in user_lists[user_id]:
        user_lists[user_id].append(list_name)
        save_success = save_users(active_users, user_lists)
        print(f"Save success: {save_success}")  # Debug print
        print(f"User lists after adding: {user_lists}")  # Debug print
        await message.reply(f"Added '{list_name}' to your active lists!")
    else:
        await message.reply(f"List '{list_name}' is already in your active lists!")

@dp.message(Command('remlist'))
async def remove_list(message: types.Message, command: CommandObject):
    """Remove a word list from user's active lists"""
    active_users, user_lists = load_active_users_and_lists()
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

@dp.message(Command('list'))
async def show_list_words(message: types.Message, command: CommandObject):
    """Show words in a specified list or user's active lists"""
    active_users, user_lists = load_active_users_and_lists()
    user_id = message.from_user.id
    
    # If list name provided, show that specific list
    if command.args:
        list_name = command.args.strip().lower()
        available_lists = get_available_wordlists()
        
        if list_name not in available_lists:
            lists = ", ".join(available_lists)
            await message.reply(
                f"Word list '{list_name}' not found!\n"
                f"Available lists: {lists}"
            )
            return
            
        try:
            words = load_words([list_name])
            words_text = "\n".join(f"• {word}" for word in sorted(words))
            
            # Split message if it's too long
            if len(words_text) > 4000:
                await message.reply(f"📚 Words in '{list_name}' (showing first 100):\n\n" + 
                                  "\n".join(f"• {word}" for word in sorted(words)[:100]) +
                                  "\n\n(List truncated due to length)")
            else:
                await message.reply(f"📚 Words in '{list_name}':\n\n{words_text}")
                
        except Exception as e:
            logging.error(f"Error showing word list: {e}")
            await message.reply("Error loading word list!")
            
    # If no list specified, show words from user's active lists
    else:
        if user_id not in user_lists:
            await message.reply("You're not subscribed! Use /start first.")
            return
            
        selected_lists = user_lists.get(user_id, DEFAULT_WORDLIST)
        for list_name in selected_lists:
            try:
                words = load_words([list_name])
                words_text = "\n".join(f"• {word}" for word in sorted(words[:20]))
                await message.reply(
                    f"📚 Sample words from '{list_name}' (first 20):\n\n{words_text}\n\n"
                    f"Use /list {list_name} to see full list"
                )
            except Exception as e:
                logging.error(f"Error showing word list '{list_name}': {e}")

@dp.message()
async def handle_any_message(message: types.Message):
    """Handle any unrecognized message or command"""
    active_users, user_lists = load_active_users_and_lists()
    user_id = message.from_user.id
    if user_id not in active_users and user_id not in user_lists:
        await message.reply("You're not subscribed! Use /start first.")
        return
    
    available_lists = get_available_wordlists()
    available_lists_text = "\n".join(f"• {lst}" for lst in sorted(available_lists))

    await message.reply(
        "Available commands:\n"
        "/stop - Unsubscribe from daily words\n"
        "/skip - Get new words immediately\n"
        "/lists - Show your active lists\n"
        "/addlist <name> - Add a list\n"
        "/remlist <name> - Remove a list\n"
        "/list - Show words in current list\n\n"
        "Available lists\n"
        f"{available_lists_text}\n"
        "Use /addlist <list_name> to add a list.\n"
        "Use /remlist <list_name> to remove a list."
    )

async def main():
    # Initialize scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_word, 'interval', seconds=300)
    scheduler.start()
    
    # Delete webhook before polling
    await bot.delete_webhook(drop_pending_updates=True)
    # Start polling
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main()) 