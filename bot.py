import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher()

# Command handler for /start
@dp.message(Command('start'))
async def send_welcome(message: types.Message):
    await message.reply("Hello! I'm your Telegram bot.")

# Message handler for regular messages
@dp.message()
async def echo_message(message: types.Message):
    await message.reply(message.text)

# Main function to start the bot
async def main():
    # Delete webhook before polling
    await bot.delete_webhook(drop_pending_updates=True)
    # Start polling
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main()) 