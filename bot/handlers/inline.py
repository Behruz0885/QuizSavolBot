from aiogram import Router
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

router = Router()

@router.inline_query()
async def inline_quiz(iq: InlineQuery):
    q = (iq.query or "").strip()
    if not q.startswith("quiz_"):
        await iq.answer([], cache_time=1)
        return

    public_code = q.replace("quiz_", "", 1).strip()
    if not public_code:
        await iq.answer([], cache_time=1)
        return

    # ✅ AUTOSTART: xabar yuborilishi bilan poll_quiz.py dagi CommandStart(deep_link=True) ishga tushadi
    # Biz groupga /start quiz_CODE yuboramiz
    msg_text = f"/start quiz_{public_code}"

    result = InlineQueryResultArticle(
        id=f"autostart_{public_code}",
        title=f"Start Quiz in this Group",
        description="Send to group and it will start instantly",
        input_message_content=InputTextMessageContent(message_text=msg_text),
    )

    await iq.answer([result], cache_time=0)
