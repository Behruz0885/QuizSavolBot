import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.config import load_config
from bot.db import init_db
from bot.handlers import setup_routers

async def main():
    logging.basicConfig(level=logging.INFO)
    cfg = load_config()
    await init_db()

    bot = Bot(token=cfg.bot_token)  # parse_mode hozircha yo‘q

    dp = Dispatcher()
    setup_routers(dp)

    logging.info("Bot started. Polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
