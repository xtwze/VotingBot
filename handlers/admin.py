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


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


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


@router.message(CreatePoll.waiting_artist_name)
async def process_artist_name(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.add_poll_option(data["poll_id"], message.text.strip())
    await state.set_state(CreatePoll.adding_options)
    await message.answer(text.ARTIST_ADDED, reply_markup=ctrl.add_artist_kb(), parse_mode="HTML")


@router.callback_query(F.data == "poll:finish", CreatePoll.adding_options)
async def cb_finish_poll(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    poll_id = data.get("poll_id")

    options = await db.get_poll_options(poll_id)
    if not options:
        await callback.answer(text.POLL_NEED_OPTIONS, show_alert=True)
        return

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

    from main import active_poll_messages  # Импорт внутри функции, чтобы избежать ошибок

    for user in users:
        try:
            sent_msg = await bot.send_message(
                user["user_id"],
                msg_text,
                reply_markup=kb,
                parse_mode="HTML"
            )
            # Добавляем сообщение в список для "Live-обновления"
            active_poll_messages[(sent_msg.chat.id, sent_msg.message_id)] = poll["id"]
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