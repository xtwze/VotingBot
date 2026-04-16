import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_IDS
import db
from handlers import user_router, admin_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)



# Хранилище сообщений опроса: {(chat_id, message_id): poll_id}
active_poll_messages: dict[tuple[int, int], int] = {}


async def refresh_poll_messages(bot: Bot):
    """Обновляет inline-кнопки с голосами каждые 2 секунды."""
    import controller as ctrl
    import text

    while True:
        await asyncio.sleep(2)
        if not active_poll_messages:
            continue

        poll = await db.get_active_poll()
        if not poll:
            active_poll_messages.clear()
            continue

        options = await db.get_poll_options(poll["id"])
        kb = ctrl.poll_options_kb(poll["id"], options)
        msg_text = text.poll_message(poll["title"], options)

        dead = []
        for (chat_id, msg_id), p_id in list(active_poll_messages.items()):
            if p_id != poll["id"]:
                dead.append((chat_id, msg_id))
                continue
            try:
                await bot.edit_message_text(
                    msg_text,
                    chat_id=chat_id,
                    message_id=msg_id,
                    reply_markup=kb,
                    parse_mode="HTML",
                )
            except Exception:
                dead.append((chat_id, msg_id))

        for key in dead:
            active_poll_messages.pop(key, None)



def _patch_user_handler():
    """
    Патчим send_active_poll в handlers/user, чтобы регистрировать
    отправленные сообщения с опросом для live-обновлений.
    """
    import handlers.user as user_mod

    original = user_mod.send_active_poll

    async def patched(target, user_id: int):
        import db as _db
        import text as _text
        import controller as _ctrl
        from aiogram.types import Message, CallbackQuery

        poll = await _db.get_active_poll()
        if not poll:
            no_poll = _text.NO_ACTIVE_POLL
            if isinstance(target, Message):
                await target.answer(no_poll)
            else:
                await target.message.answer(no_poll)
            return

        options = await _db.get_poll_options(poll["id"])
        msg_text = _text.poll_message(poll["title"], options)
        kb = _ctrl.poll_options_kb(poll["id"], options)

        if isinstance(target, Message):
            sent = await target.answer(msg_text, reply_markup=kb, parse_mode="HTML")
        else:
            sent = await target.message.answer(msg_text, reply_markup=kb, parse_mode="HTML")

        active_poll_messages[(sent.chat.id, sent.message_id)] = poll["id"]

    user_mod.send_active_poll = patched



async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан в .env")
    if not ADMIN_IDS:
        raise ValueError("ADMIN_IDS не задан в .env")

    await db.init_db()
    logger.info("База данных инициализирована")

    _patch_user_handler()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin_router)
    dp.include_router(user_router)

    # Запуск фоновой задачи обновления голосов
    asyncio.create_task(refresh_poll_messages(bot))

    logger.info("Бот запущен. Админы: %s", ADMIN_IDS)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())