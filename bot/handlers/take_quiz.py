from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.db import get_published_quiz_by_code, get_questions_for_quiz

router = Router()


def render_question(q, idx: int, total: int) -> str:
    # q: (id, q_text, opt_a, opt_b, opt_c, opt_d, correct, explanation)
    _, text, a, b, c, d, _, _ = q
    return (
        f"Q{idx+1}/{total}: {text}\n\n"
        f"A) {a}\n"
        f"B) {b}\n"
        f"C) {c}\n"
        f"D) {d}"
    )


def answer_kb(quiz_id: int, q_index: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    for letter in ["A", "B", "C", "D"]:
        kb.button(text=letter, callback_data=f"ans:{quiz_id}:{q_index}:{letter}")
    kb.adjust(4)
    return kb.as_markup()

@router.callback_query(F.data.startswith("ans:"))
async def on_answer(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    questions = data.get("questions")
    if not questions:
        await cb.answer("No active quiz.", show_alert=True)
        return

    # ans:<quiz_id>:<q_index>:<letter>
    try:
        _, quiz_id_s, q_index_s, letter = cb.data.split(":")
        quiz_id = int(quiz_id_s)
        q_index = int(q_index_s)
        letter = letter.upper()
    except Exception:
        await cb.answer("Bad data.", show_alert=True)
        return

    # faqat hozirgi savol uchun javob qabul qilamiz
    if data.get("active_quiz_id") != quiz_id or data.get("q_index") != q_index:
        await cb.answer("This question is no longer active.", show_alert=True)
        return

    q = questions[q_index]
    correct_letter = (q[6] or "").upper()
    explanation = (q[7] or "").strip()

    correct_count = int(data.get("correct_count", 0))
    if letter == correct_letter:
        correct_count += 1
        feedback = "✅ Correct!"
    else:
        feedback = f"❌ Wrong. Correct: {correct_letter}"

    if explanation:
        feedback += f"\n\nℹ️ {explanation}"

    # eski tugmalarni o'chirib qo'yamiz (double click bo'lmasin)
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await cb.answer()

    next_index = q_index + 1
    total = int(data.get("total", len(questions)))

    await state.update_data(correct_count=correct_count, q_index=next_index)

    if next_index >= total:
        title = data.get("quiz_title", "Quiz")
        await state.clear()
        score = round((correct_count / total) * 100) if total else 0
        await cb.message.answer(
            f"🏁 Finished: {title}\n"
            f"✅ Correct: {correct_count}/{total}\n"
            f"🎯 Score: {score}%"
        )
        return

    next_q = questions[next_index]
    text = feedback + "\n\n" + render_question(next_q, next_index, total)
    await cb.message.answer(text, reply_markup=answer_kb(quiz_id, next_index))
