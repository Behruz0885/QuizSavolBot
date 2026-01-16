import aiosqlite
import random
import string
from typing import Optional, Tuple

DB_PATH = "quizbot.sqlite3"

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tg_id INTEGER UNIQUE NOT NULL,
  settings_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS quizzes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_tg_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  quiz_id INTEGER NOT NULL,
  q_text TEXT NOT NULL,
  opt_a TEXT NOT NULL,
  opt_b TEXT NOT NULL,
  opt_c TEXT NOT NULL,
  opt_d TEXT NOT NULL,
  correct TEXT NOT NULL,
  explanation TEXT,
  FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_quizzes_owner ON quizzes(owner_tg_id);
CREATE INDEX IF NOT EXISTS idx_questions_quiz ON questions(quiz_id);
"""

def _gen_public_code(length: int = 5) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))

async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA_SQL)

        # ✅ Migration: eski DB bo‘lsa ham public_code qo‘shib yuboradi
        try:
            await db.execute("ALTER TABLE quizzes ADD COLUMN public_code TEXT")
        except Exception:
            pass

        # unique index (bo‘lsa ham qayta yaratmaydi)
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_quiz_public_code ON quizzes(public_code)")

        await db.commit()

async def ensure_user(tg_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users(tg_id) VALUES (?)", (tg_id,))
        await db.commit()

async def create_quiz_draft(owner_tg_id: int, title: str) -> int:
    # ✅ unique code olishga urinamiz (collision bo‘lsa yana generatsiya)
    async with aiosqlite.connect(DB_PATH) as db:
        for _ in range(10):
            code = _gen_public_code(5)
            try:
                cur = await db.execute(
                    "INSERT INTO quizzes(owner_tg_id, title, status, public_code) VALUES (?, ?, 'draft', ?)",
                    (owner_tg_id, title, code),
                )
                await db.commit()
                return int(cur.lastrowid)
            except Exception:
                # unique collision bo‘lishi mumkin
                continue

        # fallback: uzunroq code
        code = _gen_public_code(8)
        cur = await db.execute(
            "INSERT INTO quizzes(owner_tg_id, title, status, public_code) VALUES (?, ?, 'draft', ?)",
            (owner_tg_id, title, code),
        )
        await db.commit()
        return int(cur.lastrowid)

async def update_quiz_description(quiz_id: int, description: Optional[str]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE quizzes SET description = ? WHERE id = ?",
            (description, quiz_id),
        )
        await db.commit()

async def delete_quiz(quiz_id: int, owner_tg_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM quizzes WHERE id = ? AND owner_tg_id = ?",
            (quiz_id, owner_tg_id),
        )
        await db.commit()

async def add_question(
    quiz_id: int,
    q_text: str,
    opt_a: str,
    opt_b: str,
    opt_c: str,
    opt_d: str,
    correct: str,
    explanation: Optional[str],
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO questions(quiz_id, q_text, opt_a, opt_b, opt_c, opt_d, correct, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (quiz_id, q_text, opt_a, opt_b, opt_c, opt_d, correct, explanation),
        )
        await db.commit()
        return int(cur.lastrowid)

async def publish_quiz(quiz_id: int, owner_tg_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE quizzes SET status='published' WHERE id=? AND owner_tg_id=?",
            (quiz_id, owner_tg_id),
        )
        await db.commit()

# ✅ Rasmdagi menyu uchun kerak bo‘ladigan helperlar:

async def count_questions(quiz_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (quiz_id,))
        row = await cur.fetchone()
        return int(row[0]) if row else 0

async def get_quiz_brief(quiz_id: int, owner_tg_id: int) -> Optional[Tuple[int, str, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, title, COALESCE(public_code,'') FROM quizzes WHERE id=? AND owner_tg_id=?",
            (quiz_id, owner_tg_id),
        )
        row = await cur.fetchone()
        return row  # (id, title, public_code) yoki None
async def get_published_quiz_by_code(public_code: str):
    """
    public_code bo‘yicha faqat published quizni topadi.
    Return: (quiz_id, title) yoki None
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, title FROM quizzes WHERE public_code=? AND status='published'",
            (public_code,),
        )
        return await cur.fetchone()

async def get_questions_for_quiz(quiz_id: int):
    """
    Quiz savollarini olib beradi.
    Return rows:
    (id, q_text, opt_a, opt_b, opt_c, opt_d, correct, explanation)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT id, q_text, opt_a, opt_b, opt_c, opt_d, correct, COALESCE(explanation,'')
            FROM questions
            WHERE quiz_id=?
            ORDER BY id ASC
            """,
            (quiz_id,),
        )
        return await cur.fetchall()
import json

DEFAULT_SETTINGS = {
    "language": "en",          # en / uz (xohlasangiz keyin ko‘paytiramiz)
    "shuffle": True,           # On/Off
    "time_limit": 30,          # seconds
    "negative_marking": False  # Yes/No
}

async def get_user_settings(tg_id: int) -> dict:
    await ensure_user(tg_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT settings_json FROM users WHERE tg_id=?", (tg_id,))
        row = await cur.fetchone()

    try:
        data = json.loads(row[0] or "{}") if row else {}
    except Exception:
        data = {}

    # defaultlarni to‘ldiramiz
    merged = DEFAULT_SETTINGS.copy()
    merged.update({k: v for k, v in data.items() if k in merged})
    return merged

async def set_user_settings(tg_id: int, settings: dict) -> None:
    await ensure_user(tg_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET settings_json=? WHERE tg_id=?",
            (json.dumps(settings, ensure_ascii=False), tg_id),
        )
        await db.commit()

async def reset_user_settings(tg_id: int) -> None:
    await set_user_settings(tg_id, DEFAULT_SETTINGS.copy())
import json

DEFAULT_SETTINGS = {
    "time_limit": 30,  # seconds (5..300)
}

async def get_user_settings(tg_id: int) -> dict:
    # users jadvali bor, ensure_user sizda bor
    await ensure_user(tg_id)

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT settings_json FROM users WHERE tg_id=?", (tg_id,))
        row = await cur.fetchone()

    try:
        data = json.loads(row[0] or "{}") if row else {}
    except Exception:
        data = {}

    merged = DEFAULT_SETTINGS.copy()
    if isinstance(data, dict):
        merged.update({k: v for k, v in data.items() if k in merged})
    return merged

async def set_user_time_limit(tg_id: int, seconds: int) -> None:
    seconds = int(seconds)
    if seconds < 5:
        seconds = 5
    if seconds > 300:
        seconds = 300

    s = await get_user_settings(tg_id)
    s["time_limit"] = seconds

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET settings_json=? WHERE tg_id=?",
            (json.dumps(s, ensure_ascii=False), tg_id),
        )
        await db.commit()
