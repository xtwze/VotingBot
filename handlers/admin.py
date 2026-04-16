import asyncio

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import db
import text
import controller as ctrl
from config import ADMIN_IDS
from states import CreatePoll, Broadcast

router = Router()


async def is_admin(user_id: int) -> bool:
    # Проверка по списку из config.py
    if user_id in ADMIN_IDS:
        return True

    # Проверка по базе данных
    db_admins = await db.get_admins()  # Тут нужен await, поэтому и функция async
    return user_id in db_admins

# --- Вход в админку ---
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer(text.NOT_ADMIN)
        return
    await state.clear()
    await message.answer(text.ADMIN_PANEL, reply_markup=ctrl.admin_panel_kb(), parse_mode="HTML")


# ── Возврат в админ-панель ────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:back")
async def cb_admin_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    await state.clear()  # Сбрасываем состояния, если админ был в процессе создания опроса или рассылки
    await callback.message.edit_text(
        text.ADMIN_PANEL,
        reply_markup=ctrl.admin_panel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast:edit", Broadcast.confirming)
async def cb_broadcast_edit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Broadcast.waiting_text)
    await callback.message.edit_text(
        text.ASK_BROADCAST_TEXT,
        reply_markup=ctrl.cancel_broadcast_kb(), # Добавляем и сюда
        parse_mode="HTML"
    )
    await callback.answer()
    await callback.answer()


# --- Создание опроса: Шаг 1 (Тема) ---
@router.callback_query(F.data == "admin:create_poll")
async def cb_create_poll(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    await state.set_state(CreatePoll.waiting_title)
    # Добавляем reply_markup с кнопкой назад
    await callback.message.edit_text(
        text.ASK_POLL_TITLE,
        reply_markup=ctrl.cancel_creation_kb(),
        parse_mode="HTML"
    )


@router.message(CreatePoll.waiting_title)
async def process_poll_title(message: Message, state: FSMContext):
    title = message.text.strip()

    # Перед созданием нового, подводим итоги старого
    prev = await db.get_active_poll()
    if prev:
        top = await db.get_poll_top(prev["id"])
        res_text = text.poll_results(prev["title"], top)
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(admin_id, res_text, parse_mode="HTML")
            except:
                pass

    poll_id = await db.create_poll(title)
    await state.update_data(poll_id=poll_id)
    await state.set_state(CreatePoll.adding_options)
    await message.answer(text.ASK_ARTIST, reply_markup=ctrl.add_artist_kb(), parse_mode="HTML")


# --- Создание опроса: Шаг 2 (Добавление артистов) ---
@router.callback_query(F.data == "poll:add_artist", CreatePoll.adding_options)
async def cb_add_artist_btn(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CreatePoll.waiting_artist_name)
    await callback.message.edit_text("✏️ Введите имя артиста:")


@router.message(CreatePoll.adding_options)
@router.message(CreatePoll.waiting_artist_name)  # Обрабатываем оба состояния для удобства
async def process_artist_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    # Получаем данные из состояния
    data = await state.get_data()
    poll_id = data.get("poll_id")
    artist_name = message.text.strip()

    if not artist_name:
        await message.answer("❌ Имя артиста не может быть пустым. Введите имя:")
        return

    # 1. Добавляем артиста в базу данных
    await db.add_poll_option(poll_id, artist_name)

    # 2. Переключаем состояние (на случай, если пришли из waiting_artist_name)
    await state.set_state(CreatePoll.adding_options)

    # 3. Получаем актуальный список всех уже добавленных артистов для этого опроса
    options = await db.get_poll_options(poll_id)

    # 4. Формируем текстовый список артистов
    artists_list_str = ""
    for i, opt in enumerate(options, 1):
        artists_list_str += f"{i}. <b>{opt['name']}</b>\n"

    # 5. Формируем и отправляем ответ
    reply_text = (
        f"✅ Артист <b>{artist_name}</b> успешно добавлен!\n\n"
        f"<b>Текущий список участников:</b>\n"
        f"{artists_list_str}\n"
        f"Вы можете отправить имя <u>следующего</u> артиста или завершить создание опроса кнопкой ниже 👇"
    )

    await message.answer(
        reply_text,
        reply_markup=ctrl.add_artist_kb(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "poll:finish", CreatePoll.adding_options)
async def cb_finish_poll(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    poll_id = data.get("poll_id")

    options = await db.get_poll_options(poll_id)
    if not options:
        await callback.answer("Нужно добавить хотя бы одного артиста!", show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(text.POLL_CREATED, reply_markup=ctrl.back_to_admin_kb())

    # --- ВОТ ЭТА ЧАСТЬ ОТВЕЧАЕТ ЗА РАССЫЛКУ ---
    poll = await db.get_active_poll()
    if not poll: return

    msg_text = text.poll_message(poll["title"], options)
    kb = ctrl.poll_options_kb(poll["id"], options)

    users = await db.get_all_users()
    for user in users:
        try:
            sent_msg = await bot.send_message(
                user["user_id"],
                msg_text,
                reply_markup=kb,
                parse_mode="HTML"
            )
            # Закрепляем у каждого
            await bot.pin_chat_message(sent_msg.chat.id, sent_msg.message_id, disable_notification=True)
        except Exception:
            continue

    # 1. Завершаем состояние админа
    await state.clear()
    await callback.message.edit_text(text.POLL_CREATED, reply_markup=ctrl.back_to_admin_kb())

    # 2. Получаем данные нового опроса для рассылки
    poll = await db.get_active_poll()
    if not poll:
        return

    msg_text = text.poll_message(poll["title"], options)
    kb = ctrl.poll_options_kb(poll["id"], options)

    # 3. Рассылка всем пользователям
    users = await db.get_all_users()
    sent_count = 0

    # Чтобы не импортировать active_poll_messages (из-за риска цикличности),
    # мы просто делаем рассылку.
    # Если вы хотите, чтобы эти сообщения ТОЖЕ обновлялись раз в 2 секунды,
    # их нужно добавить в словарь active_poll_messages в main.py.


    for user in users:
        try:
            sent_msg = await bot.send_message(
                user["user_id"],
                msg_text,
                reply_markup=kb,
                parse_mode="HTML"
            )
            sent_count += 1
        except Exception:
            # Пропускаем, если пользователь заблокировал бота
            pass

    await callback.message.answer(f"📢 Опрос разослан {sent_count} пользователям.")


# --- Список голосующих (Пагинация) ---
@router.callback_query(F.data.startswith("admin:voters:"))
async def cb_voters_list(callback: CallbackQuery):
    page = int(callback.data.split(":")[-1])
    poll = await db.get_active_poll()
    if not poll:
        await callback.answer("Нет активного опроса", show_alert=True)
        return

    voters = await db.get_voters(poll["id"])
    chunk, p, total = ctrl.paginate_voters(voters, page)
    await callback.message.edit_text(
        text.voters_page(chunk, p + 1, total),
        reply_markup=ctrl.voters_nav_kb(p, total),
        parse_mode="HTML"
    )


# --- Удаление голоса (команда) ---
@router.message(Command("delete_voice"))
async def cmd_delete_voice(message: Message, bot: Bot):
    if not is_admin(message.from_user.id): return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Формат: /delete_voice @username или ID")
        return

    target = args[1]
    poll = await db.get_active_poll()
    user_data = await db.find_user_by_username(target) if target.startswith("@") else await db.find_user_by_id(
        int(target))

    if user_data and poll:
        if await db.delete_vote_by_user(poll["id"], user_data["user_id"]):
            await db.block_user(user_data["user_id"])
            await message.answer(f"✅ Голос {target} удален, юзер забанен.")
            try:
                await bot.send_message(user_data["user_id"], "🚫 Ваш голос аннулирован.")
            except:
                pass
        else:
            await message.answer(text.VOTE_NOT_FOUND)
    else:
        await message.answer(text.USER_NOT_FOUND)


# --- Рассылка ---
@router.callback_query(F.data == "admin:broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    await state.set_state(Broadcast.waiting_text)
    # Добавляем кнопку назад к сообщению с просьбой ввести текст
    await callback.message.edit_text(
        text.ASK_BROADCAST_TEXT,
        reply_markup=ctrl.cancel_broadcast_kb(),  # Используем новую клавиатуру
        parse_mode="HTML"
    )
    await callback.answer()




@router.message(Broadcast.waiting_text)
async def process_broadcast(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(Broadcast.confirming)
    await message.answer(f"Предпросмотр:\n\n{message.text}", reply_markup=ctrl.broadcast_confirm_kb())


@router.callback_query(F.data == "broadcast:confirm", Broadcast.confirming)
async def cb_broadcast_send(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    users = await db.get_all_users()
    count = 0
    for u in users:
        try:
            await callback.bot.send_message(u["user_id"], data["text"])
            count += 1
        except:
            pass
    await state.clear()
    await callback.message.edit_text(f"✅ Рассылка завершена. Получили: {count}")



# --- Разблокировка юзера ---
@router.message(Command("unblock"))
async def cmd_unblock(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Введите: /unblock @username или ID")
        return

    target = args[1]
    user_data = None

    # Поиск юзера
    if target.startswith("@"):
        user_data = await db.find_user_by_username(target)
    else:
        try:
            user_data = await db.find_user_by_id(int(target))
        except ValueError:
            await message.answer("Некорректный ID.")
            return

    if user_data:
        success = await db.unblock_user(user_data["user_id"])
        if success:
            await message.answer(f"✅ Пользователь {target} разблокирован.")
            try:
                await bot.send_message(user_data["user_id"], "😇 Вы были разблокированы администратором.")
            except:
                pass
        else:
            await message.answer(text.USER_NOT_BLOCKED_OR_NOT_FOUND)
    else:
        await message.answer(text.USER_NOT_FOUND)


# --- Обработка кнопки "Удалить голос" из уведомления ---
@router.callback_query(F.data.startswith("admin_delete_vote:"))
async def cb_admin_delete_vote(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return

    # Извлекаем данные: admin_delete_vote:poll_id:user_id
    _, poll_id, user_id = callback.data.split(":")
    poll_id, user_id = int(poll_id), int(user_id)

    # Пытаемся удалить голос и заблокировать
    if await db.delete_vote_by_user(poll_id, user_id):
        await db.block_user(user_id)

        # Генерируем команду для быстрого копирования
        unblock_command = f"<code>/unblock {user_id}</code>"

        # Обновляем сообщение у админа
        await callback.message.edit_text(
            f"{callback.message.text}\n\n"
            f"🗑 <b>Голос удалён. Пользователь заблокирован.</b>\n"
            f"Разблокировать: {unblock_command} (нажмте на команду чтобы скопировать)",
            parse_mode="HTML"
        )

        # 4. Уведомляем пользователя (по желанию)
        try:
            await bot.send_message(user_id, "🚫 Ваш голос аннулирован, вы заблокированы за нарушение.")
        except:
            pass
    else:
        await callback.answer(text.VOTE_NOT_FOUND, show_alert=True)

    await callback.answer()


@router.message(Command("add_admin"))
async def cmd_add_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(text.NOT_ADMIN)
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("📝 Используйте: `/add_admin 12345678` (где цифры — это ID пользователя)")
        return

    new_admin_id = int(args[1])
    await db.add_admin(new_admin_id)

    await message.answer(f"✅ Пользователь <code>{new_admin_id}</code> теперь администратор.", parse_mode="HTML")

    # Попытка уведомить нового админа
    try:
        await message.bot.send_message(new_admin_id, "🎉 Вам выданы права администратора. Используйте /admin для входа.")
    except:
        pass


# --- Проверка перед завершением ---
@router.callback_query(F.data == "admin:close_poll_check")
async def cb_close_poll_check(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    poll = await db.get_active_poll()
    if not poll:
        await callback.answer("❌ Нет активных опросов.", show_alert=True)
        return

    options = await db.get_poll_options(poll["id"])

    # Формируем информацию о текущем опросе
    info_text = (
        f"🏁 <b>Завершение опроса</b>\n\n"
        f"Тема: <b>{poll['title']}</b>\n"
        f"Текущие голоса:\n"
    )
    for opt in options:
        info_text += f"• {opt['name']} — {opt['votes']}\n"

    info_text += "\nВы уверены, что хотите закрыть этот опрос? Больше никто не сможет проголосовать."

    await callback.message.edit_text(
        info_text,
        reply_markup=ctrl.confirm_close_poll_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# --- Подтверждение завершения ---
@router.callback_query(F.data == "admin:close_poll_confirm")
async def cb_close_poll_confirm(callback: CallbackQuery, bot: Bot):
    if not await is_admin(callback.from_user.id):
        return

    poll = await db.get_active_poll()
    if poll:
        # 1. Получаем итоги для рассылки
        top = await db.get_poll_top(poll["id"])
        res_text = text.poll_results(poll["title"], top)

        # 2. Закрываем в базе (нужно добавить функцию в db.py, если её нет)
        await db.close_poll(poll["id"])

        # 3. Рассылаем итоги всем
        users = await db.get_all_users()
        for u in users:
            try:
                await bot.send_message(u["user_id"], f"📊 <b>Опрос завершен!</b>\n\n{res_text}", parse_mode="HTML")
            except:
                continue

        await callback.message.edit_text("✅ Опрос успешно закрыт, итоги разосланы.")
    else:
        await callback.message.edit_text("❌ Опрос уже был закрыт.")

    # Возврат в админку через 2 секунды (опционально)
    await asyncio.sleep(2)
    await cmd_admin(callback.message, None)  # Вызов функции админки