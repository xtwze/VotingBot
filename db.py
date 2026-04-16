import aiosqlite
import asyncio
from typing import Optional

DB_PATH = "bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                is_blocked  INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS polls (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                is_active   INTEGER DEFAULT 1,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
                         CREATE TABLE IF NOT EXISTS admins
                         (
                             user_id
                             INTEGER
                             PRIMARY
                             KEY
                         )
                         """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS poll_options (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id     INTEGER NOT NULL,
                name        TEXT NOT NULL,
                FOREIGN KEY (poll_id) REFERENCES polls(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id     INTEGER NOT NULL,
                option_id   INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(poll_id, user_id),
                FOREIGN KEY (poll_id)   REFERENCES polls(id),
                FOREIGN KEY (option_id) REFERENCES poll_options(id),
                FOREIGN KEY (user_id)   REFERENCES users(user_id)
            )
        """)
        await db.commit()


# ── Users ─────────────────────────────────────────────────────────────────────

async def upsert_user(user_id: int, username: Optional[str]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, username) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username",
            (user_id, username),
        )
        await db.commit()


async def is_blocked(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT is_blocked FROM users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return bool(row and row[0])


async def block_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_blocked=1 WHERE user_id=?", (user_id,)
        )
        await db.commit()


async def get_all_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, username FROM users WHERE is_blocked=0"
        ) as cur:
            rows = await cur.fetchall()
    return [{"user_id": r[0], "username": r[1]} for r in rows]


# ── Polls ─────────────────────────────────────────────────────────────────────

async def get_active_poll() -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, title FROM polls WHERE is_active=1 LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "title": row[1]}


async def create_poll(title: str) -> int:
    """Деактивирует текущий опрос и создаёт новый. Возвращает id."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE polls SET is_active=0 WHERE is_active=1")
        cur = await db.execute(
            "INSERT INTO polls (title) VALUES (?)", (title,)
        )
        poll_id = cur.lastrowid
        await db.commit()
    return poll_id


async def add_poll_option(poll_id: int, name: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO poll_options (poll_id, name) VALUES (?, ?)",
            (poll_id, name),
        )
        option_id = cur.lastrowid
        await db.commit()
    return option_id


async def get_poll_options(poll_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT po.id, po.name,
                   COUNT(v.id) AS votes
            FROM poll_options po
            LEFT JOIN votes v ON v.option_id = po.id
            WHERE po.poll_id = ?
            GROUP BY po.id
            ORDER BY po.id
            """,
            (poll_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [{"id": r[0], "name": r[1], "votes": r[2]} for r in rows]


async def get_poll_top(poll_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT po.name, COUNT(v.id) AS votes
            FROM poll_options po
            LEFT JOIN votes v ON v.option_id = po.id
            WHERE po.poll_id = ?
            GROUP BY po.id
            ORDER BY votes DESC
            LIMIT 3
            """,
            (poll_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [{"name": r[0], "votes": r[1]} for r in rows]


async def get_last_inactive_poll() -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, title FROM polls WHERE is_active=0 ORDER BY id DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
    return {"id": row[0], "title": row[1]} if row else None


# ── Votes ─────────────────────────────────────────────────────────────────────

async def has_voted(poll_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM votes WHERE poll_id=? AND user_id=?",
            (poll_id, user_id),
        ) as cur:
            return await cur.fetchone() is not None


async def cast_vote(poll_id: int, option_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO votes (poll_id, option_id, user_id) VALUES (?,?,?)",
            (poll_id, option_id, user_id),
        )
        await db.commit()


async def get_voters(poll_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT u.user_id, u.username, po.name AS option_name
            FROM votes v
            JOIN users u ON u.user_id = v.user_id
            JOIN poll_options po ON po.id = v.option_id
            WHERE v.poll_id = ?
            ORDER BY v.created_at
            """,
            (poll_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [{"user_id": r[0], "username": r[1], "option_name": r[2]} for r in rows]


async def delete_vote_by_user(poll_id: int, user_id: int) -> bool:
    """Удаляет голос. Возвращает True если голос был."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM votes WHERE poll_id=? AND user_id=?",
            (poll_id, user_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def get_vote_info(poll_id: int, user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT u.username, po.name
            FROM votes v
            JOIN users u ON u.user_id = v.user_id
            JOIN poll_options po ON po.id = v.option_id
            WHERE v.poll_id=? AND v.user_id=?
            """,
            (poll_id, user_id),
        ) as cur:
            row = await cur.fetchone()
    return {"username": row[0], "option_name": row[1]} if row else None


async def find_user_by_username(username: str) -> Optional[dict]:
    clean = username.lstrip("@")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, username FROM users WHERE username=?", (clean,)
        ) as cur:
            row = await cur.fetchone()
    return {"user_id": row[0], "username": row[1]} if row else None


async def find_user_by_id(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, username FROM users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
    return {"user_id": row[0], "username": row[1]} if row else None


async def unblock_user(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE users SET is_blocked = 0 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()
        return cur.rowcount > 0




async def add_admin(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
        await db.commit()

async def get_admins() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM admins") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]