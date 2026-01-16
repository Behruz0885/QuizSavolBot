from aiogram.types import (
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def start_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⚙ Settings", callback_data="open_settings")
    kb.button(text="🤔 Help", callback_data="open_help")
    kb.adjust(2)
    kb.button(text="❌ Close", callback_data="close_message")
    kb.adjust(2, 1)
    return kb.as_markup()


def quiz_build_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Create a Question", callback_data="cq_add_one")
    kb.button(text="✅ Done", callback_data="cq_done")
    kb.button(text="❌ Cancel", callback_data="cq_cancel")
    kb.adjust(1, 2)
    return kb.as_markup()


def quiz_created_kb(bot_username: str, public_code: str) -> InlineKeyboardMarkup:
    """
    ✅ Quiz created successfully! xabaridan keyin chiqadigan 3 ta tugma:
    - Start this Quiz (CALLBACK) -> private chatda darrov boshlaydi
    - Start Quiz in Group (INLINE SWITCH) -> guruh tanlab, o‘sha guruhga start-post yuboradi
    - Share Quiz (URL) -> deep link
    """
    bot_username = (bot_username or "").lstrip("@")
    share_link = f"https://t.me/{bot_username}?start=quiz_{public_code}"

    kb = InlineKeyboardBuilder()
    kb.button(text="Start this Quiz", callback_data=f"pq_start:{public_code}")  # ✅ callback

    # ✅ Guruhga boshlash: inline rejim orqali chat tanlash oynasi chiqadi
    kb.button(text="Start Quiz in Group", switch_inline_query=f"quiz_{public_code}")

    kb.button(text="Share Quiz", url=share_link)

    kb.adjust(1, 1, 1)
    return kb.as_markup()


# --------- Reply keyboard (pastdagi menyu) ---------

def kb_cancel() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="/Cancel")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def kb_cancel_skip() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="/Cancel"), KeyboardButton(text="/Skip")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def kb_cancel_done() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="/Cancel"), KeyboardButton(text="/Done")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def kb_remove() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
