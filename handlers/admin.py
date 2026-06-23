import asyncio
from aiogram import F
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InputMediaPhoto

import db
import text
import controller as ctrl
from config import ADMIN_IDS
from states import CreatePoll, Broadcast
from urllib.parse import urlparse

router = Router()


async def is_admin(user_id: int) -> bool:
    # 1. Проверка по списку из config.py (статические админы)
    if user_id in ADMIN_IDS:
        return True

    # 2. Проверка по таблице admins в БД (динамические админы)
    db_admins = await db.get_admins()
    return user_id in db_admins

# --- Вход в админку ---
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer(text.NOT_ADMIN)
        return

    await state.clear()

    # Получаем статистику
    total_users = await db.get_total_users()
    active_users = await db.get_active_users()
    voted_current = await db.get_voted_in_current_poll()

    # Формируем текст с подставленными значениями
    panel_text = text.ADMIN_PANEL.format(
        total_users=total_users,
        active_users=active_users,
        voted_current=voted_current
    )

    await message.answer(panel_text, reply_markup=ctrl.admin_panel_kb(), parse_mode="HTML")


# ── Возврат в админ-панель ────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:back")
async def cb_admin_back(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await state.clear()

    total_users = await db.get_total_users()
    active_users = await db.get_active_users()
    voted_current = await db.get_voted_in_current_poll()

    panel_text = text.ADMIN_PANEL.format(
        total_users=total_users,
        active_users=active_users,
        voted_current=voted_current
    )

    await callback.message.edit_text(
        panel_text,
        reply_markup=ctrl.admin_panel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast:edit", Broadcast.confirming)
async def cb_broadcast_edit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Broadcast.waiting_text)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    data = await state.get_data()
    await callback.message.answer(
        text.ASK_BROADCAST_TEXT,
        reply_markup=ctrl.broadcast_compose_kb(has_button=bool(data.get("btn_url"))),
        parse_mode="HTML"
    )
    await callback.answer()


# --- Создание опроса: Шаг 1 (Тема) ---
@router.callback_query(F.data == "admin:create_poll")
async def cb_create_poll(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
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
    if not await is_admin(message.from_user.id):
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
    if not await is_admin(message.from_user.id): return
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
    if not await is_admin(callback.from_user.id):
        return

    await state.update_data(text=None, photos=[], caption_entities=None, btn_text=None, btn_url=None)
    await state.set_state(Broadcast.waiting_text)
    await callback.message.edit_text(
        text.ASK_BROADCAST_TEXT,
        reply_markup=ctrl.broadcast_compose_kb(has_button=False),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(Broadcast.waiting_text, F.media_group_id)
async def process_broadcast_album(message: Message, state: FSMContext):
    """Обработка альбома (несколько фото одним сообщением)"""
    data = await state.get_data()
    photos: list[str] = data.get("photos") or []

    if len(photos) >= text.MAX_BROADCAST_PHOTOS:
        await message.answer(text.BROADCAST_PHOTO_LIMIT)
        return

    # Добавляем фото (в альбоме message.photo содержит текущее фото)
    photo_id = message.photo[-1].file_id
    if photo_id not in photos:
        photos.append(photo_id)

    current_text = data.get("text")
    update_payload = {"photos": photos}

    # Берём подпись из первого сообщения альбома
    if message.caption and not current_text:
        current_text = message.caption
        update_payload["text"] = current_text
        update_payload["caption_entities"] = message.caption_entities

    await state.update_data(**update_payload)

    # Чтобы не спамить уведомлениями на каждый файл альбома — отвечаем только один раз
    if message.media_group_id and len(photos) == 1:  # первое фото в группе
        data = await state.get_data()
        await message.answer(
            text.broadcast_status(current_text, len(photos), btn_text=data.get("btn_text"), btn_url=data.get("btn_url")),
            reply_markup=ctrl.broadcast_compose_kb(has_button=bool(data.get("btn_url"))),
            parse_mode="HTML"
        )
    await message.answer("📸 Фото добавлено в альбом")


@router.message(Broadcast.waiting_text, F.photo)
async def process_broadcast_photo(message: Message, state: FSMContext):
    """Одиночное фото"""
    data = await state.get_data()
    photos: list[str] = data.get("photos") or []

    if len(photos) >= text.MAX_BROADCAST_PHOTOS:
        await message.answer(
            text.BROADCAST_PHOTO_LIMIT,
            reply_markup=ctrl.broadcast_compose_kb()
        )
        return

    photos.append(message.photo[-1].file_id)

    current_text = data.get("text")
    update_payload = {"photos": photos}

    if message.caption and not current_text:
        current_text = message.caption
        update_payload["text"] = current_text
        update_payload["caption_entities"] = message.caption_entities

    await state.update_data(**update_payload)

    data = await state.get_data()
    await message.answer(
        text.broadcast_status(current_text, len(photos), btn_text=data.get("btn_text"), btn_url=data.get("btn_url")),
        reply_markup=ctrl.broadcast_compose_kb(has_button=bool(data.get("btn_url"))),
        parse_mode="HTML"
    )


@router.message(Broadcast.waiting_text, F.text)
async def process_broadcast_text(message: Message, state: FSMContext):
    await state.update_data(
        text=message.text,
        caption_entities=message.entities
    )
    data = await state.get_data()
    photos = data.get("photos") or []

    await message.answer(
        text.broadcast_status(message.text, len(photos), btn_text=data.get("btn_text"), btn_url=data.get("btn_url")),
        reply_markup=ctrl.broadcast_compose_kb(has_button=bool(data.get("btn_url"))),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "broadcast:add_button", Broadcast.waiting_text)
async def cb_broadcast_add_button(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Broadcast.waiting_button_text)
    await callback.message.answer(
        text.ASK_BUTTON_TEXT,
        reply_markup=ctrl.cancel_button_input_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(Broadcast.waiting_button_text, F.text)
async def process_button_text(message: Message, state: FSMContext):
    await state.update_data(btn_text=message.text.strip())
    await state.set_state(Broadcast.waiting_button_url)
    await message.answer(
        text.ASK_BUTTON_URL,
        reply_markup=ctrl.cancel_button_input_kb(),
        parse_mode="HTML"
    )


@router.message(Broadcast.waiting_button_url, F.text)
async def process_button_url(message: Message, state: FSMContext):
    url = message.text.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        await message.answer(text.BUTTON_INVALID_URL, parse_mode="HTML")
        return

    await state.update_data(btn_url=url)
    await state.set_state(Broadcast.waiting_text)

    data = await state.get_data()
    photos = data.get("photos") or []
    await message.answer(
        text.BUTTON_ADDED + "\n\n" + text.broadcast_status(
            data.get("text"), len(photos), btn_text=data.get("btn_text"), btn_url=url
        ),
        reply_markup=ctrl.broadcast_compose_kb(has_button=True),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "broadcast:remove_button", Broadcast.waiting_text)
async def cb_broadcast_remove_button(callback: CallbackQuery, state: FSMContext):
    await state.update_data(btn_text=None, btn_url=None)
    data = await state.get_data()
    photos = data.get("photos") or []
    await callback.message.answer(
        text.BUTTON_REMOVED + "\n\n" + text.broadcast_status(data.get("text"), len(photos)),
        reply_markup=ctrl.broadcast_compose_kb(has_button=False),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast:cancel_button")
async def cb_broadcast_cancel_button(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Broadcast.waiting_text)
    data = await state.get_data()
    photos = data.get("photos") or []
    await callback.message.answer(
        text.broadcast_status(
            data.get("text"), len(photos),
            btn_text=data.get("btn_text"), btn_url=data.get("btn_url")
        ),
        reply_markup=ctrl.broadcast_compose_kb(has_button=bool(data.get("btn_url"))),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast:done", Broadcast.waiting_text)
async def cb_broadcast_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    broadcast_text = data.get("text")
    photos: list[str] = data.get("photos") or []
    caption_entities = data.get("caption_entities")
    btn_text = data.get("btn_text")
    btn_url = data.get("btn_url")

    if not broadcast_text and not photos:
        await callback.answer(text.BROADCAST_EMPTY, show_alert=True)
        return

    await state.set_state(Broadcast.confirming)

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Клавиатура поста (если задана кнопка)
    post_kb = ctrl.broadcast_post_button_kb(btn_text, btn_url) if btn_text and btn_url else None

    # Предпросмотр с сохранением форматирования
    if not photos:
        await callback.message.answer(broadcast_text, entities=caption_entities, reply_markup=post_kb)
    elif len(photos) == 1:
        await callback.message.answer_photo(
            photos[0],
            caption=broadcast_text,
            caption_entities=caption_entities,
            reply_markup=post_kb
        )
    else:
        media = [InputMediaPhoto(media=p) for p in photos]
        if broadcast_text:
            media[0].caption = broadcast_text
            media[0].caption_entities = caption_entities
        await callback.message.answer_media_group(media)
        # Для альбома кнопку прикрепляем отдельным сообщением в предпросмотре
        if post_kb:
            await callback.message.answer("☝️ К посту будет прикреплена кнопка выше.", reply_markup=post_kb)

    await callback.message.answer(
        text.BROADCAST_PREVIEW,
        reply_markup=ctrl.broadcast_confirm_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast:confirm", Broadcast.confirming)
async def cb_broadcast_send(callback: CallbackQuery, state: FSMContext):
    # Сразу убираем кнопки и показываем, что процесс пошёл
    try:
        await callback.message.edit_text(
            "⏳ <b>Рассылка запущена...</b>\n\n"
            "Пожалуйста, подождите :)",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await callback.answer("Рассылка началась", show_alert=False)

    data = await state.get_data()
    broadcast_text = data.get("text")
    photos: list[str] = data.get("photos") or []
    caption_entities = data.get("caption_entities")
    btn_text = data.get("btn_text")
    btn_url = data.get("btn_url")
    post_kb = ctrl.broadcast_post_button_kb(btn_text, btn_url) if btn_text and btn_url else None

    users = await db.get_all_users()
    total_users = len(users)
    count = 0
    errors = 0

    # --- Сама рассылка ---
    for u in users:
        try:
            if not photos:
                await callback.bot.send_message(
                    u["user_id"],
                    broadcast_text,
                    entities=caption_entities,
                    reply_markup=post_kb
                )
            elif len(photos) == 1:
                await callback.bot.send_photo(
                    u["user_id"],
                    photos[0],
                    caption=broadcast_text,
                    caption_entities=caption_entities,
                    reply_markup=post_kb
                )
            else:
                media = [InputMediaPhoto(media=p) for p in photos]
                if broadcast_text:
                    media[0].caption = broadcast_text
                    media[0].caption_entities = caption_entities
                await callback.bot.send_media_group(u["user_id"], media)
                if post_kb:
                    await callback.bot.send_message(u["user_id"], "👇", reply_markup=post_kb)

            count += 1

            # Небольшая задержка, чтобы не попасть под лимиты Telegram
            await asyncio.sleep(0.045)  # ~28-30 сообщений в секунду

        except Exception:
            errors += 1
            # Пропускаем заблокированных и т.д.

    # --- Финальное сообщение ---
    result_text = (
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"✅ Успешно доставлено: <b>{count}</b> из {total_users}\n"
        f"❌ Ошибок: {errors}"
    )

    try:
        await callback.message.edit_text(result_text, parse_mode="HTML")
    except Exception:
        # Если не получилось отредактировать — отправляем новое
        await callback.message.answer(result_text, parse_mode="HTML")

    await state.clear()
    await callback.answer()



# --- Разблокировка юзера ---
@router.message(Command("unblock"))
async def cmd_unblock(message: Message, bot: Bot):
    if not await is_admin(message.from_user.id):
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
    if not await is_admin(callback.from_user.id):
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
    if not await is_admin(message.from_user.id):
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
                await bot.send_message(u["user_id"], f" 🏁<b>Опрос завершен!</b>\n\n{res_text}", parse_mode="HTML")
            except:
                continue

        await callback.message.edit_text("✅ Опрос успешно закрыт, итоги разосланы.")
    else:
        await callback.message.edit_text("❌ Опрос уже был закрыт.")