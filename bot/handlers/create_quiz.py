from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.states import CreateQuiz
from bot.keyboards import (
    quiz_build_kb,
    quiz_created_kb,
    kb_cancel,
    kb_cancel_skip,
    kb_cancel_done,
    kb_remove,
)
from bot.utils_parser import parse_quiz_text
from bot.db import (
    create_quiz_draft,
    update_quiz_description,
    delete_quiz,
    add_question,
    publish_quiz,
    count_questions,
    get_quiz_brief,
)

router = Router()

INSTRUCTION_TEXT = (
    "Check out the 🎥 Tutorial Videos in the bot's Preview Section:\n"
    "Click on the bot's profile picture. Scroll down and click Preview.\n\n"
    "<b>There are four ways to create a quiz:</b>\n\n"
    "👉 <b>(1). Using the Create a Question Button</b>\n"
    "- Click the Create a Question button.\n"
    "- Type your question and add 4 answer options.\n\n"
    "👉 <b>(2). Forwarding Quizzes from Channels, Groups, or Bots</b>\n"
    "- You can forward existing quizzes to this bot.\n\n"
    "👉 <b>(3). From Text or a .txt File</b>\n"
    "- Use the following format to submit your questions:\n\n"
    "1. Question text\n"
    "A. Option 1\n"
    "B. Option 2\n"
    "C. Option 3\n"
    "D. Option 4\n"
    "Answer Option Number\n"
    "Explanation (optional)\n\n"
    "<b>Example:</b>\n"
    "1. How many continents are there in the world?\n"
    "A. 17\n"
    "B. 7\n"
    "C. 6\n"
    "D. 1\n"
    "2\n"
    "Asia, Africa, North America, South America, Antarctica, Europe, and Australia.\n\n"
    "👉 <b>(4). Using AI</b>\n"
    "- Type a prompt starting with: <code>ai:</code>\n\n"
    "You can submit all questions at once or one by one.\n"
    "Type /done when finished.\n"
    "Or Click /cancel to Cancel it."
)


async def go_to_question_mode(message: Message, state: FSMContext):
    await state.set_state(CreateQuiz.waiting_questions)

    # 1) Inline menu (Create Question / Done / Cancel)
    await message.answer(INSTRUCTION_TEXT, reply_markup=quiz_build_kb(), parse_mode="HTML")

    # 2) Pastki reply keyboard (Cancel/Done)
    await message.answer("Choose an option below:", reply_markup=kb_cancel_done())


async def send_quiz_created_menu(bot: Bot, owner_tg_id: int, quiz_id: int, chat_id: int):
    total = await count_questions(quiz_id)
    if total <= 0:
        await bot.send_message(chat_id, "You haven't added any questions yet.")
        return

    brief = await get_quiz_brief(quiz_id, owner_tg_id)
    if not brief:
        await bot.send_message(chat_id, "Quiz not found.")
        return

    _, title, public_code = brief

    me = await bot.get_me()
    username = me.username or ""

    text = (
        "✅ <b>Quiz created successfully!</b>\n\n"
        f"<b>Quiz ID:</b> <code>{public_code}</code>\n"
        f"<b>Quiz Title:</b> {title}\n"
        f"<b>Total Questions:</b> {total}"
    )

    await bot.send_message(
        chat_id,
        text,
        parse_mode="HTML",
        reply_markup=quiz_created_kb(username, public_code),
    )


# -------------------- COMMANDS --------------------

@router.message(Command("create_quiz"))
async def create_quiz(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(CreateQuiz.waiting_title)
    await message.answer(
        "Please provide a Title for the quiz:\nOr Click /cancel to Cancel it",
        reply_markup=kb_cancel(),
    )


@router.message(Command("cancel", "Cancel"))
async def cancel_any(message: Message, state: FSMContext):
    data = await state.get_data()
    quiz_id = data.get("draft_quiz_id")
    if quiz_id:
        await delete_quiz(quiz_id, message.from_user.id)

    await state.clear()
    await message.answer("Cancelled.", reply_markup=kb_remove())


@router.message(Command("done", "Done"))
async def done_cmd(message: Message, state: FSMContext):
    """
    /done bosilganda ham rasmdagidek menyu chiqadi.
    """
    data = await state.get_data()
    quiz_id = data.get("draft_quiz_id")
    if not quiz_id:
        await message.answer("You haven't added any questions yet.")
        return

    total = await count_questions(quiz_id)
    if total <= 0:
        await message.answer("You haven't added any questions yet.")
        return

    await publish_quiz(quiz_id, message.from_user.id)
    await state.clear()

    # pastki menyuni olib tashlaymiz
    await message.answer("✅ Finishing...", reply_markup=kb_remove())
    await send_quiz_created_menu(message.bot, message.from_user.id, quiz_id, message.chat.id)


# -------------------- TITLE / DESCRIPTION --------------------

@router.message(CreateQuiz.waiting_title)
async def got_title(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    if not title:
        await message.answer("Title cannot be empty. Please provide a Title:", reply_markup=kb_cancel())
        return

    quiz_id = await create_quiz_draft(message.from_user.id, title)
    await state.update_data(draft_quiz_id=quiz_id)

    await state.set_state(CreateQuiz.waiting_description)
    await message.answer(
        "Please provide a Description for the quiz:\nOr Click /cancel to Cancel it Or /skip",
        reply_markup=kb_cancel_skip(),
    )


@router.message(Command("skip", "Skip"), CreateQuiz.waiting_description)
async def skip_description(message: Message, state: FSMContext):
    data = await state.get_data()
    quiz_id = data.get("draft_quiz_id")
    if quiz_id:
        await update_quiz_description(quiz_id, None)
    await go_to_question_mode(message, state)


@router.message(CreateQuiz.waiting_description)
async def got_description(message: Message, state: FSMContext):
    desc = (message.text or "").strip()
    data = await state.get_data()
    quiz_id = data.get("draft_quiz_id")
    if quiz_id:
        await update_quiz_description(quiz_id, desc if desc else None)
    await go_to_question_mode(message, state)


# -------------------- INLINE BUTTONS (Create Question / Done / Cancel) --------------------

@router.callback_query(F.data == "cq_cancel")
async def cq_cancel(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    quiz_id = data.get("draft_quiz_id")
    if quiz_id:
        await delete_quiz(quiz_id, cb.from_user.id)
    await state.clear()
    await cb.answer()
    await cb.message.answer("Cancelled.", reply_markup=kb_remove())


@router.callback_query(F.data == "cq_done")
async def cq_done(cb: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    quiz_id = data.get("draft_quiz_id")
    if not quiz_id:
        await cb.answer("No draft quiz.", show_alert=True)
        return

    total = await count_questions(quiz_id)
    if total <= 0:
        await cb.answer("Add at least 1 question first.", show_alert=True)
        return

    await publish_quiz(quiz_id, cb.from_user.id)
    await state.clear()
    await cb.answer()

    # pastki reply menyuni olib tashlaymiz
    await cb.message.answer("✅ Finishing...", reply_markup=kb_remove())
    await send_quiz_created_menu(bot, cb.from_user.id, quiz_id, cb.message.chat.id)


@router.callback_query(F.data == "cq_add_one")
async def cq_add_one(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(CreateQuiz.q_text)
    await cb.message.answer("Type your question text:\nOr Click /cancel to Cancel it", reply_markup=kb_cancel())


# -------------------- TXT IMPORT --------------------

@router.message(CreateQuiz.waiting_questions, F.document)
async def import_txt_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc:
        return

    name = (doc.file_name or "").lower()
    if not name.endswith(".txt"):
        await message.answer("Please send a .txt file.", reply_markup=kb_cancel_done())
        return

    data = await state.get_data()
    quiz_id = data.get("draft_quiz_id")
    if not quiz_id:
        await message.answer("No draft quiz found. Use /create_quiz first.", reply_markup=kb_remove())
        return

    file = await bot.get_file(doc.file_id)
    file_bytes = await bot.download_file(file.file_path)
    content = file_bytes.read()

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("cp1251")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="replace")

    questions, errors = parse_quiz_text(text)
    if errors:
        msg = "❌ TXT format error:\n" + "\n".join(errors[:5])
        if len(errors) > 5:
            msg += f"\n...and {len(errors)-5} more."
        await message.answer(msg, reply_markup=kb_cancel_done())
        return

    if not questions:
        await message.answer("❌ No questions found in the file.", reply_markup=kb_cancel_done())
        return

    added = 0
    for q in questions:
        await add_question(
            quiz_id=quiz_id,
            q_text=q["q_text"],
            opt_a=q["opt_a"],
            opt_b=q["opt_b"],
            opt_c=q["opt_c"],
            opt_d=q["opt_d"],
            correct=q["correct"],
            explanation=q["explanation"],
        )
        added += 1

    await message.answer(f"✅ Imported {added} questions from .txt", reply_markup=kb_cancel_done())


# -------------------- 1-BY-1 QUESTION FLOW --------------------

@router.message(CreateQuiz.q_text)
async def q_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text:
        await message.answer("Question cannot be empty. Type again:", reply_markup=kb_cancel())
        return
    await state.update_data(q_text=text)
    await state.set_state(CreateQuiz.opt_a)
    await message.answer("Option A:", reply_markup=kb_cancel())


@router.message(CreateQuiz.opt_a)
async def opt_a(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    if not t:
        await message.answer("Option A cannot be empty. Type again:", reply_markup=kb_cancel())
        return
    await state.update_data(opt_a=t)
    await state.set_state(CreateQuiz.opt_b)
    await message.answer("Option B:", reply_markup=kb_cancel())


@router.message(CreateQuiz.opt_b)
async def opt_b(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    if not t:
        await message.answer("Option B cannot be empty. Type again:", reply_markup=kb_cancel())
        return
    await state.update_data(opt_b=t)
    await state.set_state(CreateQuiz.opt_c)
    await message.answer("Option C:", reply_markup=kb_cancel())


@router.message(CreateQuiz.opt_c)
async def opt_c(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    if not t:
        await message.answer("Option C cannot be empty. Type again:", reply_markup=kb_cancel())
        return
    await state.update_data(opt_c=t)
    await state.set_state(CreateQuiz.opt_d)
    await message.answer("Option D:", reply_markup=kb_cancel())


@router.message(CreateQuiz.opt_d)
async def opt_d(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    if not t:
        await message.answer("Option D cannot be empty. Type again:", reply_markup=kb_cancel())
        return
    await state.update_data(opt_d=t)
    await state.set_state(CreateQuiz.correct)
    await message.answer("Correct answer? (A/B/C/D or 1/2/3/4)", reply_markup=kb_cancel())


@router.message(CreateQuiz.correct)
async def correct(message: Message, state: FSMContext):
    raw = (message.text or "").strip().upper()
    mapping = {"1": "A", "2": "B", "3": "C", "4": "D", "A": "A", "B": "B", "C": "C", "D": "D"}
    if raw not in mapping:
        await message.answer("Please enter A/B/C/D or 1/2/3/4:", reply_markup=kb_cancel())
        return
    await state.update_data(correct=mapping[raw])
    await state.set_state(CreateQuiz.explanation)
    await message.answer("Explanation (optional). Type /skip to skip.", reply_markup=kb_cancel_skip())


@router.message(Command("skip", "Skip"), CreateQuiz.explanation)
async def skip_expl(message: Message, state: FSMContext):
    data = await state.get_data()
    quiz_id = data.get("draft_quiz_id")
    if not quiz_id:
        await message.answer("No draft quiz found. Use /create_quiz first.", reply_markup=kb_remove())
        await state.clear()
        return

    await add_question(
        quiz_id=quiz_id,
        q_text=data["q_text"],
        opt_a=data["opt_a"],
        opt_b=data["opt_b"],
        opt_c=data["opt_c"],
        opt_d=data["opt_d"],
        correct=data["correct"],
        explanation=None,
    )

    await state.set_state(CreateQuiz.waiting_questions)
    await message.answer("✅ Question added.", reply_markup=kb_cancel_done())
    await message.answer("Menu:", reply_markup=quiz_build_kb())


@router.message(CreateQuiz.explanation)
async def expl(message: Message, state: FSMContext):
    explanation = (message.text or "").strip() or None
    data = await state.get_data()
    quiz_id = data.get("draft_quiz_id")
    if not quiz_id:
        await message.answer("No draft quiz found. Use /create_quiz first.", reply_markup=kb_remove())
        await state.clear()
        return

    await add_question(
        quiz_id=quiz_id,
        q_text=data["q_text"],
        opt_a=data["opt_a"],
        opt_b=data["opt_b"],
        opt_c=data["opt_c"],
        opt_d=data["opt_d"],
        correct=data["correct"],
        explanation=explanation,
    )

    await state.set_state(CreateQuiz.waiting_questions)
    await message.answer("✅ Question added.", reply_markup=kb_cancel_done())
    await message.answer("Menu:", reply_markup=quiz_build_kb())


# -------------------- WAITING QUESTIONS (fallback) --------------------

@router.message(CreateQuiz.waiting_questions)
async def waiting_questions(message: Message, state: FSMContext):
    # Inline menu
    await message.answer(
        "Choose an option:\n➕ Create a Question / ✅ Done / ❌ Cancel",
        reply_markup=quiz_build_kb(),
    )
    # Pastki reply menu
    await message.answer("Commands:", reply_markup=kb_cancel_done())
