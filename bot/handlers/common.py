from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()

@router.callback_query(F.data == "close_message")
async def close_message(cb: CallbackQuery):
    # xabarni o‘chirishga urinamiz
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.answer()

@router.callback_query(F.data == "open_help")
async def open_help(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "Help:\n"
        "/create_quiz - quiz yaratish\n"
        "/cancel - jarayonni bekor qilish\n"
        "Keyinroq: savol qo‘shish, /done, share va hokazo."
    )
