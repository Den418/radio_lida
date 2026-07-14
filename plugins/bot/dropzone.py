"""
Плагин: просто кинь аудио боту

Работает в личных сообщениях боту и в LOG_GROUP, если она настроена,
без всяких команд.

Админ: файл сразу уходит в очередь.
Обычный человек: файл уходит в предложения, админ решит сам через /admin.
"""
from pyrogram import filters
from pyrogram.types import Message

from bot_client import bot
from config import Config
from utils import CHAT_ID, LOG_GROUP, SUGGESTIONS_PER_USER_LIMIT, mp


def _dropzone_filter():
    """Личка боту плюс, если настроена, LOG_GROUP, и это аудио, голосовое или аудио-документ."""
    media = filters.audio | filters.voice | filters.document
    if LOG_GROUP:
        return (filters.private | filters.chat(LOG_GROUP)) & media
    return filters.private & media


@bot.on_message(_dropzone_filter())
async def auto_queue_dropped_media(client, message: Message):
    """Любое аудио, присланное напрямую без команды, попадает в дело."""

    if message.caption and message.caption.startswith("/"):
        return  # этим уже занимается play.py

    media = message.audio or message.voice or message.document

    if message.document:
        mime = message.document.mime_type or ""
        if not mime.startswith("audio/"):
            return

    if media is None or not message.from_user:
        return

    if message.voice:
        title = f"Голосовое от {message.from_user.first_name}"
    else:
        title = getattr(media, "title", None) or getattr(media, "file_name", None) or "Без названия"

    admins = await mp.get_admins(CHAT_ID)
    is_admin = message.from_user.id in admins

    if is_admin:
        song = [message.id, title, media.file_id, "telegram", message.from_user.mention, None]
        pos = await mp.add_to_queue(song)
        k = await message.reply_text(f"Добавил в очередь: {title}. Позиция {pos}.")
        await mp.delete_after_delay(k)
        return

    item = mp.add_suggestion(title, media.file_id, "telegram", message.from_user, None)
    if item is None:
        await message.reply_text(
            f"У тебя уже накопилось {SUGGESTIONS_PER_USER_LIMIT} предложений без ответа, "
            f"подожди, пока админ их рассмотрит."
        )
        return

    await message.reply_text(f"Спасибо, передал администратору: {title}")

    if LOG_GROUP:
        try:
            await bot.send_message(
                LOG_GROUP,
                f"Новое предложение от {message.from_user.mention}: {title}\n"
                f"Открой /admin, там в разделе «Предложения» можно принять или отклонить.",
            )
        except Exception:
            pass
