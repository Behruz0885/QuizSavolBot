from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.db import set_user_time_limit

router = Router()

@router.message(Command("time"))
async def set_time(message: Message):
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Use: /time 30  (5..300 seconds)")
        return
    await set_user_time_limit(message.from_user.id, int(parts[1]))
    await message.answer(f"✅ Time limit set to {parts[1]} sec")
