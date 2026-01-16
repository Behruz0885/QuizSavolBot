from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Tuple, List, Any, Optional, Union

from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, PollAnswer, CallbackQuery
from aiogram.enums import PollType

from bot.db import (
    get_published_quiz_by_code,
    get_questions_for_quiz,
    get_user_settings,
)

router = Router()

# Session key:
# - private chat: ("p", chat_id, user_id)
# - group chat:   ("g", chat_id)
SessionKey = Union[Tuple[str, int, int], Tuple[str, int]]

# poll_id -> (session_key, message_id, step_id)
POLL_INDEX: Dict[str, Tuple[SessionKey, int, int]] = {}


@dataclass
class Session:
    quiz_id: int
    title: str
    questions: List[Tuple[Any, ...]]  # (id, q_text, opt_a, opt_b, opt_c, opt_d, correct, explanation)

    q_index: int = 0
    seconds: int = 30
    step_id: int = 0  # har savol yuborilganda +1

    # step_id -> {user_id: chosen_idx}
    answers: Dict[int, Dict[int, int]] = field(default_factory=dict)

    # step_id -> correct_idx (0..3)
    correct_by_step: Dict[int, int] = field(default_factory=dict)

    # user timing
    first_seen: Dict[int, float] = field(default_factory=dict)
    last_seen: Dict[int, float] = field(default_factory=dict)

    # user display name (username/fullname)
    display: Dict[int, str] = field(default_factory=dict)


SESSIONS: Dict[SessionKey, Session] = {}


# Telegram limitlari:
# - Poll question: 1..300
# - Poll option: 1..100
# - Explanation: 0..200
def _truncate(text: str, max_len: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _session_key(chat_type: str, chat_id: int, user_id: int) -> SessionKey:
    if chat_type in ("group", "supergroup"):
        return ("g", chat_id)
    return ("p", chat_id, user_id)


def _clamp_open_period(seconds: int) -> int:
    # Telegram open_period: 5..600
    if seconds < 5:
        return 5
    if seconds > 600:
        return 600
    return seconds


def _fmt_duration(sec: float) -> str:
    sec = int(max(0, sec))
    m, s = divmod(sec, 60)
    return f"{m} мин {s} сек"


def _build_leaderboard_text(session: Session) -> str:
    total_q = len(session.questions)

    # user_id -> correct_count
    score: Dict[int, int] = {}

    for step_id, user_map in session.answers.items():
        correct_idx = session.correct_by_step.get(step_id)
        if correct_idx is None:
            continue

        for uid, chosen_idx in user_map.items():
            # init
            score.setdefault(uid, 0)
            if chosen_idx == correct_idx:
                score[uid] += 1

    rows = []
    for uid, correct in score.items():
        name = session.display.get(uid, str(uid))
        t0 = session.first_seen.get(uid)
        t1 = session.last_seen.get(uid)
        duration = (t1 - t0) if (t0 is not None and t1 is not None) else 10**9
        rows.append((uid, name, correct, duration))

    # sort: ko'p to'g'ri -> yuqorida, teng bo'lsa tezroq -> yuqorida
    rows.sort(key=lambda x: (-x[2], x[3]))

    out: List[str] = []
    out.append(f"✅ Тест «{session.title}» закончен!")
    out.append("")
    out.append(f"Вы ответили на {total_q} вопросов")
    out.append("")

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    if not rows:
        out.append("Пока нет ответов 😅")
        return "\n".join(out)

    for idx, (_, name, correct, duration) in enumerate(rows[:15], start=1):
        prefix = medals.get(idx, f"{idx}.")
        out.append(f"{prefix} {name} — {correct} ({_fmt_duration(duration)})")

    out.append("")
    out.append("🏆 Поздравляем победителей!")
    return "\n".join(out)


def _to_options(q_row) -> Tuple[str, List[str], int, Optional[str]]:
    # Question
    q_text = _truncate((q_row[1] or ""), 300)

    # Options (prefix A/B/C/D qo‘shamiz, shuning uchun avval 97 gacha kesamiz)
    raw_opts = [
        _truncate((q_row[2] or ""), 97),
        _truncate((q_row[3] or ""), 97),
        _truncate((q_row[4] or ""), 97),
        _truncate((q_row[5] or ""), 97),
    ]

    # bo‘sh bo‘lsa "-" bilan to‘ldiramiz
    raw_opts = [o if o else "-" for o in raw_opts]

    letters = ["A) ", "B) ", "C) ", "D) "]
    opts = [letters[i] + raw_opts[i] for i in range(4)]

    # Correct (A/B/C/D)
    correct_letter = (q_row[6] or "A").strip().upper()
    letter_to_idx = {"A": 0, "B": 1, "C": 2, "D": 3}
    correct_idx = letter_to_idx.get(correct_letter, 0)
    correct_idx = max(0, min(3, correct_idx))

    # Explanation
    explanation = _truncate((q_row[7] or ""), 200).strip()
    if not explanation:
        explanation = None

    if not q_text:
        q_text = "Question"

    return q_text, opts, correct_idx, explanation


async def _schedule_next(bot: Bot, s_key: SessionKey, step_id: int, seconds: int):
    """Har savol uchun: seconds tugagandan keyin keyingi savol yuboriladi (javoblar bo‘lsa ham)."""
    await asyncio.sleep(seconds)
    try:
        session = SESSIONS.get(s_key)
        if not session:
            return

        if session.step_id != step_id:
            return

        await _send_next_or_finish(bot, s_key)

    except Exception as e:
        logging.exception("schedule_next failed: %s", e)


async def _send_next_or_finish(bot: Bot, s_key: SessionKey):
    session = SESSIONS.get(s_key)
    if not session:
        return

    chat_id = s_key[1]  # ("g", chat_id) yoki ("p", chat_id, user_id)
    total = len(session.questions)

    session.q_index += 1

    if session.q_index >= total:
        # ✅ Leaderboard yuboramiz (guruhda ham, private’da ham ishlaydi)
        await bot.send_message(chat_id, _build_leaderboard_text(session))
        SESSIONS.pop(s_key, None)
        return

    await send_poll_question(bot, s_key, session)


async def send_poll_question(bot: Bot, s_key: SessionKey, session: Session):
    chat_id = s_key[1]

    q = session.questions[session.q_index]
    q_text, opts, correct_idx, explanation = _to_options(q)

    seconds = _clamp_open_period(int(session.seconds))
    question_title = _truncate(f"{session.q_index + 1}. {q_text}", 300)

    msg = await bot.send_poll(
        chat_id=chat_id,
        question=question_title,
        options=opts,
        is_anonymous=False,
        type=PollType.QUIZ,           # ✅ QUIZ MODE
        correct_option_id=correct_idx,
        explanation=explanation,      # ✅ None bo‘lsa yubormaydi
        allows_multiple_answers=False,
        open_period=seconds,          # ✅ 30s tugagach o‘zi yopiladi
    )

    session.step_id += 1
    step_id = session.step_id

    # ✅ har savolning to'g'ri javobini step_id bo‘yicha saqlaymiz
    session.correct_by_step[step_id] = correct_idx

    POLL_INDEX[msg.poll.id] = (s_key, msg.message_id, step_id)

    asyncio.create_task(_schedule_next(bot, s_key, step_id, seconds))


async def _start_session(
    bot: Bot,
    chat_type: str,
    chat_id: int,
    user_id: int,
    public_code: str,
    reply_to: Optional[Message] = None,
):
    quiz = await get_published_quiz_by_code(public_code)
    if not quiz:
        text = "❌ Quiz not found or not published."
        if reply_to:
            await reply_to.answer(text)
        else:
            await bot.send_message(chat_id, text)
        return

    quiz_id, title = quiz
    questions = await get_questions_for_quiz(quiz_id)
    if not questions:
        text = "❌ This quiz has no questions."
        if reply_to:
            await reply_to.answer(text)
        else:
            await bot.send_message(chat_id, text)
        return

    s = await get_user_settings(user_id)
    seconds = int(s.get("time_limit", 30))

    s_key = _session_key(chat_type, chat_id, user_id)

    if s_key in SESSIONS:
        await bot.send_message(chat_id, "⚠️ A quiz is already running here. Please wait for it to finish.")
        return

    SESSIONS[s_key] = Session(quiz_id=quiz_id, title=title, questions=questions, seconds=seconds)

    await bot.send_message(chat_id, f"▶ Starting: {title}\n⏳ Each question: {seconds} sec")
    await send_poll_question(bot, s_key, SESSIONS[s_key])


# ✅ Private deep-link: /start quiz_xxxxx
    parts = (message.text or "").split(maxsplit=1)
    payload = parts[1].strip() if len(parts) == 2 else ""
    if not payload.startswith("quiz_"):
        return

    public_code = payload.replace("quiz_", "", 1).strip()
    await _start_session(bot, message.chat.type, message.chat.id, message.from_user.id, public_code, reply_to=message)


# ✅ "Start this Quiz" callback (private chat)
@router.callback_query(F.data.startswith("pq_start:"))
async def start_poll_from_button(cb: CallbackQuery, bot: Bot):
    public_code = cb.data.split(":", 1)[1].strip()
    await cb.answer()
    await _start_session(bot, cb.message.chat.type, cb.message.chat.id, cb.from_user.id, public_code)


# ✅ GROUP START: /quiz <code>
@router.message(Command("quiz"))
async def start_quiz_in_group(message: Message, bot: Bot):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Use: /quiz <code>\nExample: /quiz sfPlk")
        return

    code = parts[1].strip()
    if code.startswith("quiz_"):
        code = code.replace("quiz_", "", 1).strip()

    await _start_session(bot, message.chat.type, message.chat.id, message.from_user.id, code, reply_to=message)


@router.poll_answer()
async def on_poll_answer(poll_answer: PollAnswer, bot: Bot):
    poll_id = poll_answer.poll_id
    info = POLL_INDEX.get(poll_id)
    if not info:
        return

    s_key, message_id, step_id = info
    session = SESSIONS.get(s_key)
    if not session:
        return

    if session.step_id != step_id:
        return

    user_id = poll_answer.user.id
    chosen = poll_answer.option_ids[0] if poll_answer.option_ids else -1

    session.answers.setdefault(step_id, {})
    session.answers[step_id][user_id] = chosen

    # ✅ vaqt + display name yig'amiz
    now = time.time()
    u = poll_answer.user
    name = f"@{u.username}" if getattr(u, "username", None) else (u.full_name or "User")
    session.display[user_id] = name
    if user_id not in session.first_seen:
        session.first_seen[user_id] = now
    session.last_seen[user_id] = now

    # ❌ stop_poll QILMAYMIZ! Hammaniki ovoz bersin.
    return


# ✅ Guruhda oddiy /start bo'lsa yo'riqnoma
@router.message(CommandStart())
async def start_anywhere(message: Message, bot: Bot):
    parts = (message.text or "").split(maxsplit=1)
    payload = parts[1].strip() if len(parts) == 2 else ""

    if payload.startswith("quiz_"):
        public_code = payload.replace("quiz_", "", 1).strip()
        await _start_session(bot, message.chat.type, message.chat.id, message.from_user.id, public_code, reply_to=message)
        return

    if message.chat.type in ("group", "supergroup"):
        await message.answer(
            "Guruhda quiz boshlash uchun:\n"
            "`/quiz <code>`\n"
            "Masalan: `/quiz sfPlk`",
            parse_mode="Markdown"
        )


@router.message(Command("stop_quiz"))
async def stop_quiz(message: Message):
    s_key = _session_key(message.chat.type, message.chat.id, message.from_user.id)

    session = SESSIONS.pop(s_key, None)
    if not session:
        await message.answer("ℹ️ No active quiz to stop.")
        return

    session.step_id += 1
    await message.answer("🛑 Quiz stopped.")
