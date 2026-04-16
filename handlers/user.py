from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

import db
import text
import controller as ctrl

router = Router()


# Функция-заглушка, которая будет заменена в main.py для регистрации сообщений в live-обновлении
async def send_active_poll(target, user_id: int):
    pass


@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username

    if await db.is_blocked(user_id):
        await message.answer(text.BLOCKED_USER)
        return

    # Сохраняем/обновляем юзера в базе
    await db.upsert_user(user_id, username)

    # Отправляем приветствие и опрос
    await message.answer(text.WELCOME, parse_mode="HTML")
    await send_active_poll(message, user_id)


# --- Выбор варианта (первое нажатие) ---
@router.callback_query(F.data.startswith("vote:"))
async def cb_vote_choose(callback: CallbackQuery):
    user_id = callback.from_user.id
    if await db.is_blocked(user_id):
        await callback.answer(text.BLOCKED_USER, show_alert=True)
        return

    _, poll_id, option_id, option_name = callback.data.split(":", 3)
    poll_id, option_id = int(poll_id), int(option_id)

    if await db.has_voted(poll_id, user_id):
        await callback.answer(text.ALREADY_VOTED, show_alert=True)
        return

    # Меняем сообщение на подтверждение
    kb = ctrl.confirm_vote_kb(poll_id, option_id, option_name)
    await callback.message.edit_text(
        text.confirm_vote(option_name),
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


# --- Подтверждение голоса ---
@router.callback_query(F.data.startswith("vote_confirm:"))
async def cb_vote_confirm(callback: CallbackQuery):
    from config import ADMIN_IDS

    user_id = callback.from_user.id
    username = callback.from_user.username

    if await db.is_blocked(user_id):
        await callback.answer(text.BLOCKED_USER, show_alert=True)
        return

    _, poll_id, option_id = callback.data.split(":")
    poll_id, option_id = int(poll_id), int(option_id)

    if await db.has_voted(poll_id, user_id):
        await callback.answer(text.ALREADY_VOTED, show_alert=True)
        return

    # Записываем в БД
    await db.cast_vote(poll_id, option_id, user_id)

    # Получаем данные для уведомления админов
    options = await db.get_poll_options(poll_id)
    option_name = next((o["name"] for o in options if o["id"] == option_id), "—")
    poll = await db.get_active_poll()

    await callback.message.edit_text(text.VOTE_ACCEPTED, parse_mode="HTML")
    await callback.answer()

    # Уведомление админов
    notify_text = text.admin_vote_notify(username, user_id, option_name, poll["title"])
    admin_kb = ctrl.delete_vote_kb(poll_id, user_id)

    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(admin_id, notify_text, reply_markup=admin_kb, parse_mode="HTML")
        except Exception:
            pass


# --- Возврат к списку вариантов (кнопка "Нет/Назад") ---
@router.callback_query(F.data.startswith("vote_back:"))
async def cb_vote_back(callback: CallbackQuery):
    _, poll_id = callback.data.split(":")
    poll_id = int(poll_id)

    poll = await db.get_active_poll()
    if not poll or poll["id"] != poll_id:
        await callback.answer("Опрос завершен.", show_alert=True)
        return

    options = await db.get_poll_options(poll_id)
    kb = ctrl.poll_options_kb(poll_id, options)
    await callback.message.edit_text(
        text.poll_message(poll["title"], options),
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer(text.VOTE_CANCELLED)