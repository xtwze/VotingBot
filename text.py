from __future__ import annotations
from config import CHANNEL_ID

WELCOME = (
    "👋 Привет! Добро пожаловать в бот голосований на <b>ПОСЛЕДСТВИЯ ФЕСТ 2k17</b>\n\n"
    "Здесь ты можешь проголосовать за своего любимого артиста.\n\n"
    "Кто будет выступать на фестивале - зависит от тебя!"
)
MAX_BROADCAST_PHOTOS = 10

NO_ACTIVE_POLL = "📭 Сейчас нет активных голосований. Загляни позже!"

# ── Голосование (пользователь) ──────────────────────────────────────────────
def poll_message(title: str, options: list[dict]) -> str:
    lines = [f"<b>{title}</b>\n"]
    for opt in options:
        lines.append(f"• {opt['name']} — {opt['votes']} голос(ов)")
    lines.append("\n<i>Выбери вариант ниже 👇</i>")
    return "\n".join(lines)

def confirm_vote(option_name: str) -> str:
    return (
        f"Ты выбрал(а): <b>{option_name}</b>\n\n"
        "Подтвердить голос?"
    )

VOTE_ACCEPTED = "✅ Твой голос принят! Спасибо за участие :)"
VOTE_CANCELLED = "↩️ Голосование отменено. Ты можешь выбрать снова."
ALREADY_VOTED = "⚠️ Ты уже голосовал(а) в этом опросе."

# ── Уведомление админу ───────────────────────────────────────────────────────
def admin_vote_notify(username: str, user_id: int, option_name: str, poll_title: str) -> str:
    uname = f"@{username}" if username else f"id:{user_id}"
    return (
        f"🔔 <b>Новый голос!</b>\n\n"
        f"Пользователь: {uname} (<code>{user_id}</code>)\n"
        f"Опрос: <b>{poll_title}</b>\n"
        f"Выбор: <b>{option_name}</b>"
    )

# ── Админ-панель ─────────────────────────────────────────────────────────────
ADMIN_PANEL = (
    "🔧 <b>Панель управления администратора</b>\n"
    "───────────────────\n"
    "Выберите необходимое действие в меню ниже:\n\n"

    "👥 <b>Управление пользователями:</b>\n"
    "• Чтобы <b>заблокировать</b> юзера, перейдите в список голосующих.\n"
    "• Чтобы <b>разблокировать</b>: <code>/unblock @username</code> (нажмите чтобы скопировать)\n\n"

    "🛡 <b>Настройка доступа:</b>\n"
    "• Добавить админа: <code>/add_admin ID</code>\n"
    "• Узнать свой ID: <code>/myid</code>\n\n"

    "⚠️ <i>Внимание: для добавления прав используйте только числовой ID!</i>"
    "\n\nПривет от Миши Икствизи😎"
)

# Создание опроса
ASK_POLL_TITLE = "📝 Введите тему (название) голосования:"
ASK_ARTIST = (
    "🎤 Введите имя артиста или используйте кнопки ниже:"
)
ARTIST_ADDED = "✅ Артист добавлен! Продолжайте или завершите создание"
POLL_CREATED = "🎉 Голосование успешно создано!"
POLL_NEED_OPTIONS = "⚠️ Добавьте хотя бы один вариант перед созданием опроса"

# Итоги
def poll_results(title: str, top: list[dict]) -> str:
    lines = [f"📊 <b>Итоги голосования: {title}</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, opt in enumerate(top[:3]):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        lines.append(f"{medal} {opt['name']} — {opt['votes']} голос(ов)")
    return "\n".join(lines)

# Список голосующих
def voters_page(voters: list[dict], page: int, total_pages: int) -> str:
    if not voters:
        return "👥 <b>Список голосующих пуст.</b>"
    lines = [f"👥 <b>Голосующие (стр. {page}/{total_pages}):</b>\n"]
    for v in voters:
        uname = f"@{v['username']}" if v['username'] else "—"
        lines.append(f"• {uname} | <code>{v['user_id']}</code> → <b>{v['option_name']}</b>")
    lines.append("\n<i>Чтобы аннулировать голос: /delete_voice @ник или user_id</i>")
    return "\n".join(lines)

VOTE_DELETED_ADMIN = "🗑 Голос удалён. Пользователь заблокирован в боте."
VOTE_NOT_FOUND = "❌ Голос не найден."
USER_NOT_FOUND = "❌ Пользователь не найден."


MAX_BROADCAST_PHOTOS = 10

# Рассылка
ASK_BROADCAST_TEXT = (
    "✍️ Отправьте текст и/или фото (до 10 шт.) для рассылки.\n\n"
    "Можно прислать текст, одно фото с подписью, несколько фото по очереди "
    "(или альбомом) — всё это соберётся в одну рассылку.\n"
    "Когда всё готово — нажмите «✅ Готово»."
)
BROADCAST_PREVIEW = "👁 <b>Предпросмотр сообщения:</b>\n\nПодтвердить рассылку?"
BROADCAST_SENT = "📨 Рассылка выполнена!"
BROADCAST_CANCELLED = "↩️ Рассылка отменена."
BROADCAST_PHOTO_LIMIT = "⚠️ Достигнут лимит — максимум 10 фото в одной рассылке."
BROADCAST_EMPTY = "⚠️ Добавьте текст или хотя бы одно фото перед отправкой."


def broadcast_status(text_value: str | None, photos_count: int, limit: int = MAX_BROADCAST_PHOTOS) -> str:
    lines = ["📦 <b>Черновик рассылки</b>\n"]

    if text_value:
        lines.append(f"<b>Текст:</b>\n{text_value}\n")
    else:
        lines.append("Текст: — не задан\n")

    lines.append(f"Фото: {photos_count}/{limit}")
    lines.append("\nМожете добавить ещё текст/фото или нажать «✅ Готово».")
    return "\n".join(lines)

# ── Ошибки ────────────────────────────────────────────────────────────────────
NOT_ADMIN = "🚫 У вас нет доступа к этой команде."
BLOCKED_USER = "🚫 Вы заблокированы в боте."
USER_UNBLOCKED = "✅ Пользователь разблокирован."
USER_NOT_BLOCKED_OR_NOT_FOUND = "❌ Пользователь не найден или не был заблокирован."

# ── Проверка подписки ───────────────────────────────────────────────────────
SUBSCRIBE_TEXT = (
    "👋 Привет! Добро пожаловать в бот голосований на <b>ПОСЛЕДСТВИЯ ФЕСТ 2k17</b>\n\n"
    f"Чтобы проголосовать за любимого артиста, необходимо быть подписанным на наш канал.\n\n"
    f"📢 Канал: {CHANNEL_ID}\n\n"
    "После подписки нажми кнопку ниже 👇"
)