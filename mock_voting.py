import asyncio
import aiosqlite
import random

DB_PATH = "bot.db"


async def simulate_voting():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # 1. Получаем последний активный опрос
        async with db.execute("SELECT id, title FROM polls WHERE is_active = 1 ORDER BY id DESC LIMIT 1") as cur:
            poll = await cur.fetchone()

        if not poll:
            print("❌ Активных опросов не найдено!")
            return

        print(f"📊 Голосуем в опросе: {poll['title']} (ID: {poll['id']})")

        # 2. Получаем варианты (артистов)
        async with db.execute("SELECT id, name FROM poll_options WHERE poll_id = ?", (poll['id'],)) as cur:
            options = await cur.fetchall()

        if not options:
            print("❌ В опросе нет артистов!")
            return

        option_ids = [opt['id'] for opt in options]

        # 3. Получаем список всех пользователей, которые еще НЕ голосовали в этом опросе
        async with db.execute("""
                              SELECT user_id
                              FROM users
                              WHERE user_id NOT IN (SELECT user_id FROM votes WHERE poll_id = ?)
                              """, (poll['id'],)) as cur:
            users = await cur.fetchall()

        if not users:
            print("❌ Нет доступных пользователей для голосования (все уже проголосовали).")
            return

        print(f"👥 Найдено пользователей для голосования: {len(users)}")

        # 4. Генерируем голоса
        votes_to_insert = []
        for user in users:
            # Выбираем случайного артиста
            chosen_option = random.choice(option_ids)
            votes_to_insert.append((poll['id'], chosen_option, user['user_id']))

        # 5. Массовая вставка голосов
        await db.executemany(
            "INSERT INTO votes (poll_id, option_id, user_id) VALUES (?, ?, ?)",
            votes_to_insert
        )
        await db.commit()

        print(f"✅ Успешно добавлено голосов: {len(votes_to_insert)}")


if __name__ == "__main__":
    asyncio.run(simulate_voting())