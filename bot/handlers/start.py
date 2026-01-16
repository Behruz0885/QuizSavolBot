from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards import start_kb
from bot.db import ensure_user

# ✅ poll_quiz ichidagi start funksiyani import qilamiz
from bot.handlers.poll_quiz import _start_session

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await ensure_user(message.from_user.id)

    # ✅ 1) payloadni tekshiramiz: /start quiz_xxx
    parts = (message.text or "").split(maxsplit=1)
    payload = parts[1].strip() if len(parts) == 2 else ""

    if payload.startswith("quiz_"):
        public_code = payload.replace("quiz_", "", 1).strip()
        # ✅ Agar guruh bo‘lsa ham, private bo‘lsa ham shu ishlaydi
        from aiogram import Bot
        bot: Bot = message.bot
        await _start_session(
            bot=bot,
            chat_type=message.chat.type,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            public_code=public_code,
            reply_to=message
        )
        return

    # ✅ 2) payload bo'lmasa — oddiy welcome
    text = (
        "Hello! I'm a Quiz Bot.\n\n"
        "I'm here to help you test and expand your knowledge. You can "
        "either take quizzes or create your own custom quizzes for others.\n\n"
        "/settings - Customize your quiz experience with options like ⏰ Time Limit, 🔀 Shuffle, and ✂️ Negative Marking.\n"
        "/create_quiz - Make your own Quiz\n"
        "/my_quizzes - Show your Quizzes"
    )
    await message.answer(text, reply_markup=start_kb())
