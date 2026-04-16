from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

VOTERS_PAGE_SIZE = 10




def admin_panel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать голосование", callback_data="admin:create_poll")
    builder.button(text="👥 Список голосующих",   callback_data="admin:voters:0")
    builder.button(text="📢 Рассылка",            callback_data="admin:broadcast")
    builder.adjust(1)
    return builder.as_markup()



def add_artist_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎤 Добавить артиста",       callback_data="poll:add_artist")
    builder.button(text="✅ Завершить создание опроса", callback_data="poll:finish")
    builder.adjust(1)
    return builder.as_markup()




def poll_options_kb(poll_id: int, options: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for opt in options:
        builder.button(
            text=f"{opt['name']}  [{opt['votes']}]",
            callback_data=f"vote:{poll_id}:{opt['id']}:{opt['name']}",
        )
    builder.adjust(1)
    return builder.as_markup()


def confirm_vote_kb(poll_id: int, option_id: int, option_name: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Да, голосую!",
        callback_data=f"vote_confirm:{poll_id}:{option_id}",
    )
    builder.button(
        text="↩️ Назад",
        callback_data=f"vote_back:{poll_id}",
    )
    builder.adjust(2)
    return builder.as_markup()




def delete_vote_kb(poll_id: int, user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🗑 Удалить голос",
        callback_data=f"admin_delete_vote:{poll_id}:{user_id}",
    )
    return builder.as_markup()




def voters_nav_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.button(text="⬅️", callback_data=f"admin:voters:{page - 1}")
    builder.button(text=f"{page + 1}/{total_pages}", callback_data="noop")
    if page < total_pages - 1:
        builder.button(text="➡️", callback_data=f"admin:voters:{page + 1}")
    builder.button(text="🔙 Назад", callback_data="admin:back")
    builder.adjust(3, 1)
    return builder.as_markup()


def paginate_voters(voters: list[dict], page: int):
    total_pages = max(1, (len(voters) + VOTERS_PAGE_SIZE - 1) // VOTERS_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * VOTERS_PAGE_SIZE
    chunk = voters[start: start + VOTERS_PAGE_SIZE]
    return chunk, page, total_pages




def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить",   callback_data="broadcast:confirm")
    builder.button(text="✏️ Редактировать", callback_data="broadcast:edit")
    builder.button(text="❌ Отмена",       callback_data="broadcast:cancel")
    builder.adjust(2, 1)
    return builder.as_markup()


def back_to_admin_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="admin:back")
    return builder.as_markup()