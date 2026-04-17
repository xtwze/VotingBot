import time

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile

import db
import text
import controller as ctrl
from utils import generate_captcha
from states import CaptchaState

router = Router()


# Исправленная функция отправки опроса
async def send_active_poll(message: Message, bot: Bot):
    poll = await db.get_active_poll()
    if not poll:
        # Если опроса нет, ничего не шлем или пишем "Опросов нет"
        return

    options = await db.get_poll_options(poll["id"])
    msg_text = text.poll_message(poll["title"], options)
    kb = ctrl.poll_options_kb(poll["id"], options)

    # Отправляем сообщение
    sent = await message.answer(msg_text, reply_markup=kb, parse_mode="HTML")

    # Закрепляем сообщение
    try:
        await bot.pin_chat_message(chat_id=sent.chat.id, message_id=sent.message_id, disable_notification=True)
    except Exception:
        pass


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    username = message.from_user.username

    if await db.is_blocked(user_id):
        await message.answer(text.BLOCKED_USER)
        return

    # Сохраняем/обновляем юзера в базе
    await db.upsert_user(user_id, username)

    # Путь к фото (лежит в корне проекта)
    photo = FSInputFile("Cover.jpeg")

    # Отправляем ФОТО с приветственным текстом в подписи (caption)
    await message.answer_photo(
        photo=photo,
        caption=text.WELCOME,
        parse_mode="HTML"
    )

    # Вызов отправки опроса (вторым сообщением)
    await send_active_poll(message, bot)

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




@router.callback_query(F.data.startswith("vote_confirm:"))
async def cb_vote_confirm(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if await db.is_blocked(user_id):
        await callback.answer(text.BLOCKED_USER, show_alert=True)
        return

    _, poll_id, option_id = callback.data.split(":")

    # Генерируем капчу
    question, answer = generate_captcha()

    # Сохраняем данные во временное хранилище (FSM)
    await state.update_data(
        pending_poll_id=int(poll_id),
        pending_option_id=int(option_id),
        captcha_answer=answer
    )

    await state.set_state(CaptchaState.waiting_answer)

    # Редактируем сообщение, просим решить пример
    await callback.message.edit_text(
        f"🤖<b>Проверка на человека</b>\n\n{question}",
        parse_mode="HTML"
    )
    await callback.answer()

# Добавляем обработчик ответа на капчу
@router.message(CaptchaState.waiting_answer)
async def process_captcha_answer(message: Message, state: FSMContext, bot: Bot):
    # Сразу удаляем сообщение пользователя, чтобы не засорять чат
    try:
        await message.delete()
    except:
        pass

    data = await state.get_data()
    correct_answer = data.get("captcha_answer")

    # Проверяем, ввел ли пользователь число и совпадает ли оно
    if message.text and message.text.isdigit() and int(message.text) == correct_answer:
        # --- КОД ИЗ ВАШЕГО СТАРОГО cb_vote_confirm ---
        poll_id = data.get("pending_poll_id")
        option_id = data.get("pending_option_id")
        user_id = message.from_user.id
        username = message.from_user.username

        await db.cast_vote(poll_id, option_id, user_id)

        poll = await db.get_active_poll()
        options = await db.get_poll_options(poll_id)

        # Обновляем сообщение (нужно найти старое сообщение с капчей и отредактировать его)
        # Так как мы удаляем сообщение юзера, нам нужно отредактировать последнее сообщение бота
        # Но проще отправить новое или использовать сохраненный message_id

        new_text = f"<b>{text.VOTE_ACCEPTED}</b>\n\n" + text.poll_message(poll["title"], options)
        kb = ctrl.poll_options_kb(poll_id, options)

        # Отправляем новое сообщение, так как старое сообщение с кнопками было заменено текстом капчи
        await message.answer(new_text, reply_markup=kb, parse_mode="HTML")
        await state.clear()

        # Уведомление админам
        from config import ADMIN_IDS
        option_name = next((o["name"] for o in options if o["id"] == option_id), "—")
        notify_text = text.admin_vote_notify(username, user_id, option_name, poll["title"])
        admin_kb = ctrl.delete_vote_kb(poll_id, user_id)
        for admin_id in ADMIN_IDS:
            try: await bot.send_message(admin_id, notify_text, reply_markup=admin_kb, parse_mode="HTML")
            except: pass
    else:
        # Если неверно
        await message.answer("❌ Неверно. Попробуйте проголосовать еще раз через меню.", delete_after=5)
        await state.clear()

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


@router.callback_query(F.data.startswith("poll:refresh:"))
async def cb_poll_refresh(callback: CallbackQuery, state: FSMContext):
    COOLDOWN = 3
    user_data = await state.get_data()
    last_click = user_data.get("last_refresh_time", 0)
    current_time = time.time()

    if current_time - last_click < COOLDOWN:
        remaining = int(COOLDOWN - (current_time - last_click))
        await callback.answer(f"⏳ Подожди {remaining} сек.", show_alert=True)
        return

    await state.update_data(last_refresh_time=current_time)

    poll_id = int(callback.data.split(":")[2])
    poll = await db.get_active_poll()
    if not poll or poll["id"] != poll_id:
        await callback.answer("Опрос завершен.", show_alert=True)
        return

    options = await db.get_poll_options(poll_id)
    kb = ctrl.poll_options_kb(poll_id, options)
    has_voted = await db.has_voted(poll_id, callback.from_user.id)

    prefix = f"<b>{text.VOTE_ACCEPTED}</b>\n\n" if has_voted else ""
    msg_text = prefix + text.poll_message(poll["title"], options)

    try:
        await callback.message.edit_text(msg_text, reply_markup=kb, parse_mode="HTML")
        await callback.answer("Обновлено")
    except Exception as e:
        if "message is not modified" in str(e):
            await callback.answer("Изменений нет")
        else:
            await callback.answer()



@router.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(str(message.from_user.id))