"""
Плагин: предложения от обычных пользователей

Раз обычные люди не могут сами командовать ботом, пусть хотя бы могут
предложить трек или видео. Админ увидит предложение в панели (/admin)
и решит, добавлять его в очередь или нет.

Доступно всем, без ограничений по правам.
"""
from pyrogram import filters
from pyrogram.types import Message

from bot_client import bot
from config import Config
from utils import DURATION_LIMIT, LOG_GROUP, SUGGESTIONS_PER_USER_LIMIT, mp, youtube_lookup


async def _notify_admins(title: str, user_mention: str):
    """Сообщить в служебный чат, что появилось новое предложение."""
    if not LOG_GROUP:
        return
    try:
        await bot.send_message(
            LOG_GROUP,
            f"Новое предложение от {user_mention}: {title}\n"
            f"Открой /admin, там в разделе «Предложения» можно принять или отклонить.",
            disable_notification=False,
        )
    except Exception:
        pass


@bot.on_message(filters.command(["suggest", "predlojit"]))
async def cmd_suggest(_, message: Message):
    """
    /suggest [ссылка или название]  предложить трек с YouTube
    Либо ответь этой командой на аудио, видео или голосовое сообщение.
    """
    query = " ".join(message.command[1:]).strip()
    reply = message.reply_to_message
    user = message.from_user

    if not user:
        return

    if reply and (reply.audio or reply.voice or reply.video or reply.document):
        if reply.video:
            title = reply.caption or "Видео"
            item = mp.add_suggestion(title, reply.video.file_id, "telegram_video", user, None)
        else:
            media = reply.audio or reply.voice or reply.document
            title = getattr(media, "title", None) or getattr(media, "file_name", None) or "Без названия"
            item = mp.add_suggestion(title, media.file_id, "telegram", user, None)

        if item is None:
            await message.reply_text(
                f"У тебя уже накопилось {SUGGESTIONS_PER_USER_LIMIT} предложений, "
                f"которые ещё не рассмотрели. Подожди, пока админ ответит на них."
            )
            return

        await message.reply_text(f"Спасибо, передал администратору: {title}")
        await _notify_admins(title, user.mention)
        return

    if not query:
        await message.reply_text(
            "Напиши название трека или ссылку после команды.\n\n"
            "Например: /suggest Imagine Dragons Believer\n\n"
            "Или ответь этой командой на аудио, видео или голосовое сообщение."
        )
        return

    k = await message.reply_text("Ищу...")

    info = await youtube_lookup(query)
    if not info:
        await k.edit("Не нашёл, попробуй другое название или ссылку.")
        return

    title    = info.get("title", "Без названия")
    duration = info.get("duration") or 0
    url      = info.get("webpage_url") or info.get("original_url") or info.get("url", "")
    thumb    = info.get("thumbnail")

    if duration and duration > DURATION_LIMIT * 60:
        mins = duration // 60
        await k.edit(f"Это {mins} минут, а лимит {DURATION_LIMIT}, попробуй что-то покороче.")
        return

    item = mp.add_suggestion(title, url, "youtube", message.from_user, thumb)
    if item is None:
        await k.edit(
            f"У тебя уже накопилось {SUGGESTIONS_PER_USER_LIMIT} предложений, "
            f"которые ещё не рассмотрели. Подожди, пока админ ответит на них."
        )
        return

    await k.edit(f"Спасибо, передал администратору: {title}")
    await _notify_admins(title, message.from_user.mention)
