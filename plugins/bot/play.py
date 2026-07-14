"""
Плагин: /play, /song, /playvideo — добавление треков в очередь

/play ссылка_или_название       добавляет аудио-трек с YouTube в очередь
/song ссылка_или_название       скачивает аудио и отправляет файлом в чат
/playvideo ссылка_или_название  добавляет настоящее видео со звуком и картинкой
"""
import os

from pyrogram import filters
from pyrogram.types import Message
from yt_dlp import YoutubeDL

from bot_client import bot
from config import Config
from utils import ADMINS, CHAT_ID, DURATION_LIMIT, admin_filter, mp, youtube_lookup


def _play_filter():
    """Фильтр для команд добавления треков: только админы, если включён ADMIN_ONLY."""
    base = filters.command(["play", "song", "playvideo", "pv"])
    if Config.ADMIN_ONLY:
        return base & admin_filter
    return base


@bot.on_message(_play_filter())
async def cmd_play(client, message: Message):
    """
    /play [ссылка или название]       добавить аудио-трек в очередь
    /playvideo [ссылка или название]  добавить видео со звуком и картинкой

    Можно ответить командой на аудио, видео или голосовое сообщение.
    """
    command = message.command[0]
    is_video_request = command in ("playvideo", "pv")
    query = " ".join(message.command[1:]).strip()

    reply = message.reply_to_message
    if reply and (reply.audio or reply.voice or reply.video or reply.document):

        if is_video_request and reply.video:
            title = reply.caption or "Видео"
            song = [message.id, title, reply.video.file_id, "telegram_video", message.from_user.mention, None]
            pos = await mp.add_to_queue(song)
            await message.reply_text(f"Добавил видео в очередь: {title}. Позиция {pos}.")
            return

        media = reply.audio or reply.voice or reply.document
        if media:
            title = getattr(media, "title", None) or getattr(media, "file_name", None) or "Без названия"
            song = [message.id, title, media.file_id, "telegram", message.from_user.mention, None]
            pos = await mp.add_to_queue(song)
            await message.reply_text(f"Добавил в очередь: {title}. Позиция {pos}.")
            return

    if not query:
        hint = "название или ссылку на видео" if is_video_request else "название трека или ссылку"
        await message.reply_text(
            f"Укажи {hint}.\n\n"
            f"Например:\n"
            f"/{command} Imagine Dragons Believer\n"
            f"/{command} https://youtu.be/..."
        )
        return

    if command == "song":
        k = await message.reply_text("Ищу и скачиваю...")
        os.makedirs("downloads", exist_ok=True)

        opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "default_search": "ytsearch1",
            "geo-bypass": True,
            "nocheckcertificate": True,
            "quiet": True,
            "no_warnings": True,
            "outtmpl": "downloads/%(title)s.%(ext)s",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(query, download=True)
                if "entries" in info:
                    info = info["entries"][0]
        except Exception:
            info = None

        if not info:
            await k.edit("Не нашёл трек, попробуй другой запрос.")
            return

        title = info.get("title", "Без названия")
        fname = None
        for f in os.listdir("downloads"):
            if f.endswith(".mp3") and title[:20].lower() in f.lower():
                fname = os.path.join("downloads", f)
                break

        if not fname or not os.path.isfile(fname):
            await k.edit("Файл не нашёлся после скачивания.")
            return

        await k.delete()
        await message.reply_audio(
            fname,
            title=title,
            performer=info.get("uploader", ""),
            caption=title,
        )
        try:
            os.remove(fname)
        except Exception:
            pass
        return

    k = await message.reply_text("Ищу видео..." if is_video_request else "Ищу трек...")

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
        await k.edit(
            f"Это слишком длинное, {mins} минут при лимите {DURATION_LIMIT}. "
            f"Лимит можно увеличить через MAXIMUM_DURATION в настройках."
        )
        return

    src_type = "video" if is_video_request else "youtube"
    song = [message.id, title, url, src_type, message.from_user.mention, thumb]
    pos = await mp.add_to_queue(song)

    mins, secs = divmod(duration, 60)
    icon = "🎬" if is_video_request else "🎵"

    await k.edit(
        f"{icon} Добавил в очередь: {title}\n"
        f"Длительность {mins}:{secs:02d}, запросил {message.from_user.mention}, позиция {pos}."
    )
