# ── Общие ──────────────────────────────────────────────────────────────────
WELCOME = (
    "👋 Привет! Добро пожаловать в бот голосований на <b>ПОСДЕЛСТВИЯ ФЕСТ 2k17</b>\n\n"
    "Здесь ты можешь проголосовать за своего любимого артиста.\n\n"
    "Кто будет выступать на фестивале - зависит от тебя!"
)

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

VOTE_ACCEPTED = "✅ Твой голос принят! Спасибо за участие."
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
ADMIN_PANEL = "🔧 <b>Админ-панель</b>\nВыберите действие:"

# Создание опроса
ASK_POLL_TITLE = "📝 Введите тему (название) голосования:"
ASK_ARTIST = (
    "🎤 Введите имя артиста или используйте кнопки ниже:"
)
ARTIST_ADDED = "✅ Артист добавлен! Продолжайте или завершите создание."
POLL_CREATED = "🎉 Голосование успешно создано!"
POLL_NEED_OPTIONS = "⚠️ Добавьте хотя бы один вариант перед созданием опроса."

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


# Рассылка
ASK_BROADCAST_TEXT = "✍️ Напишите сообщение для рассылки:"
BROADCAST_PREVIEW = "👁 <b>Предпросмотр сообщения:</b>\n\nПодтвердить рассылку?"
BROADCAST_SENT = "📨 Рассылка выполнена!"
BROADCAST_CANCELLED = "↩️ Рассылка отменена."

# ── Ошибки ────────────────────────────────────────────────────────────────────
NOT_ADMIN = "🚫 У вас нет доступа к этой команде."
BLOCKED_USER = "🚫 Вы заблокированы в боте."
USER_UNBLOCKED = "✅ Пользователь разблокирован."
USER_NOT_BLOCKED_OR_NOT_FOUND = "❌ Пользователь не найден или не был заблокирован."