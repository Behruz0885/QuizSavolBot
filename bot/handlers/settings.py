from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db import get_user_settings, set_user_time_limit

router = Router()


def settings_kb(time_limit: int):
    kb = InlineKeyboardBuilder()
    kb.button(text=f"⏰ Time Limit : {time_limit} sec", callback_data="set_time")
    kb.button(text="❌ Close Settings", callback_data="set_close_settings")
    kb.adjust(1, 1)
    return kb.as_markup()


async def send_settings(message: Message):
    s = await get_user_settings(message.from_user.id)
    tl = int(s.get("time_limit", 30))

    text = (
        "⚙ Config Bot Settings\n\n"
        f"⏰ Time Limit : {tl} sec"
    )
    await message.answer(text, reply_markup=settings_kb(tl))


# ✅ /settings komandasi ishlashi uchun
@router.message(Command("settings"))
async def cmd_settings(message: Message):
    await send_settings(message)


# ✅ Settings tugmasi bosilganda (callback)
@router.callback_query(F.data == "open_settings")
async def cb_open_settings(cb: CallbackQuery):
    await cb.answer()
    await send_settings(cb.message)


@router.callback_query(F.data == "set_time")
async def cb_set_time(cb: CallbackQuery):
    await cb.answer()

    s = await get_user_settings(cb.from_user.id)
    tl = int(s.get("time_limit", 30))

    options = [15, 30, 60, 90, 120]
    tl = options[(options.index(tl) + 1) % len(options)] if tl in options else 30

    await set_user_time_limit(cb.from_user.id, tl)

    # faqat knopkalarni yangilaymiz
    await cb.message.edit_reply_markup(reply_markup=settings_kb(tl))


@router.callback_query(F.data == "set_close_settings")
async def cb_close(cb: CallbackQuery):
    await cb.answer()
    try:
        await cb.message.delete()
    except Exception:
        pass
