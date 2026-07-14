"""
Плагин: административные команды

Доступны администраторам чата, людям из AUTH_USERS в конфиге и
тем, кого добавили через панель /admin.
"""
import os
import shutil

from pyrogram import filters
from pyrogram.types import Message

from bot_client import bot
from config import Config
from utils import ADMINS, CHAT_ID, call, mp, playlist, msg, ADMIN_LIST, admin_filter, Stats


def admin_only():
    """Фильтр: только администраторы, проверяется динамически (см. admin_filter в utils.py)."""
    return admin_filter


# ══════════════════════════════════════════════════════════════════════════════
#  Голосовой чат
# ══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command(["join"]) & admin_only())
async def cmd_join(_, message: Message):
    """/join — войти в голосовой чат и запустить радио."""
    k = await message.reply_text("Вхожу в голосовой чат...")
    try:
        await mp.start_radio()
        await k.edit(f"Готово, радио {Config.STREAM_URL}")
    except Exception as e:
        await k.edit(f"Не получилось: {e}")


@bot.on_message(filters.command(["leave"]) & admin_only())
async def cmd_leave(_, message: Message):
    """/leave — покинуть голосовой чат."""
    await mp.stop_radio()
    await message.reply_text("Вышел из голосового чата.")


# ══════════════════════════════════════════════════════════════════════════════
#  Управление воспроизведением
# ══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command(["radio"]) & admin_only())
async def cmd_radio(_, message: Message):
    """/radio — включить радио-поток."""
    k = await message.reply_text("Включаю радио...")
    try:
        await mp.start_radio()
        await k.edit(f"Радио включено, {Config.STREAM_URL}")
    except Exception as e:
        await k.edit(f"Не получилось: {e}")


@bot.on_message(filters.command(["stop", "stopradio"]) & admin_only())
async def cmd_stop(_, message: Message):
    """/stop, /stopradio — остановить воспроизведение."""
    await mp.stop_radio()
    await message.reply_text("Воспроизведение остановлено.")


@bot.on_message(filters.command(["skip"]) & admin_only())
async def cmd_skip(_, message: Message):
    """/skip — пропустить текущий трек."""
    if not playlist:
        await message.reply_text("Очередь пуста, нечего пропускать.")
        return
    current = playlist[0][1]
    await message.reply_text(f"Пропускаю: {current}")
    await mp.skip_current_playing()


@bot.on_message(filters.command(["pause"]) & admin_only())
async def cmd_pause(_, message: Message):
    """/pause — поставить на паузу."""
    try:
        result = await call.pause(CHAT_ID)
        if result:
            Stats.is_paused = True
            await message.reply_text("Пауза.")
        else:
            await message.reply_text("Не получилось, может уже на паузе.")
    except Exception as e:
        await message.reply_text(f"Не получилось: {e}")


@bot.on_message(filters.command(["resume"]) & admin_only())
async def cmd_resume(_, message: Message):
    """/resume — продолжить после паузы."""
    try:
        result = await call.resume(CHAT_ID)
        if result:
            Stats.is_paused = False
            await message.reply_text("Продолжаю.")
        else:
            await message.reply_text("Не получилось, может и не было на паузе.")
    except Exception as e:
        await message.reply_text(f"Не получилось: {e}")


@bot.on_message(filters.command(["replay"]) & admin_only())
async def cmd_replay(_, message: Message):
    """/replay — повторить текущий трек с начала."""
    if not playlist:
        await message.reply_text("Очередь пуста, перезапускаю радио.")
        await mp.start_radio()
        return
    song = playlist[0]
    await message.reply_text(f"Повторяю: {song[1]}")
    await mp.play_song(song)


# ══════════════════════════════════════════════════════════════════════════════
#  Информация, доступно всем
# ══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command(["current", "playing", "now"]))
async def cmd_current(_, message: Message):
    """/current — что сейчас играет."""
    if not playlist:
        await message.reply_text(f"Сейчас играет радио, {Config.STREAM_URL}")
    else:
        song = playlist[0]
        rest = len(playlist) - 1
        text = f"Сейчас играет: {song[1]}, запросил {song[4]}"
        if rest:
            text += f"\n\nВ очереди ещё {rest}"
        await message.reply_text(text)


@bot.on_message(filters.command(["playlist", "queue", "list"]))
async def cmd_playlist(_, message: Message):
    """/playlist — показать очередь треков."""
    if not playlist:
        await message.reply_text("Очередь пуста, играет радио.")
        return
    lines = [f"{i}. {x[1]}, {x[4]}" for i, x in enumerate(playlist, 1)]
    await message.reply_text(
        "Очередь треков.\n\n" + "\n".join(lines),
        disable_web_page_preview=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Звук
# ══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command(["mute"]) & admin_only())
async def cmd_mute(_, message: Message):
    """/mute — заглушить юзербота."""
    try:
        result = await call.mute(CHAT_ID)
        await message.reply_text("Заглушил." if result else "Уже заглушён.")
    except Exception as e:
        await message.reply_text(f"Не получилось: {e}")


@bot.on_message(filters.command(["unmute"]) & admin_only())
async def cmd_unmute(_, message: Message):
    """/unmute — включить звук юзербота."""
    try:
        result = await call.unmute(CHAT_ID)
        await message.reply_text("Включил звук." if result else "Звук и так был включён.")
    except Exception as e:
        await message.reply_text(f"Не получилось: {e}")


@bot.on_message(filters.command(["volume", "vol"]) & admin_only())
async def cmd_volume(_, message: Message):
    """/volume [0-200] — установить громкость, 100 это обычная."""
    args = message.command[1:]
    if not args or not args[0].isdigit():
        await message.reply_text(
            "Укажи громкость от 0 до 200, например: /volume 100\n\n"
            "0 это без звука, 100 обычная, 200 максимум."
        )
        return

    volume = int(args[0])
    if not 0 <= volume <= 200:
        await message.reply_text("Громкость должна быть от 0 до 200.")
        return

    try:
        await call.change_volume_call(CHAT_ID, volume)
        Stats.volume = volume
        filled = volume // 10
        bar = "▓" * filled + "░" * (20 - filled)
        await message.reply_text(f"Громкость {volume} процентов.\n{bar}")
    except Exception as e:
        await message.reply_text(f"Не получилось: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  Обслуживание
# ══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command(["clean"]) & admin_only())
async def cmd_clean(_, message: Message):
    """/clean — удалить скачанные файлы."""
    k = await message.reply_text("Очищаю папку загрузок...")
    try:
        if os.path.isdir("downloads"):
            shutil.rmtree("downloads")
        os.makedirs("downloads", exist_ok=True)
        await k.edit("Готово, папка загрузок очищена.")
    except Exception as e:
        await k.edit(f"Не получилось: {e}")


@bot.on_message(filters.command(["setvar"]) & admin_only())
async def cmd_setvar(_, message: Message):
    """/setvar ключ значение — изменить Config Var на Heroku."""
    if not Config.HEROKU_APP:
        await message.reply_text(
            "Heroku не настроен. Задай в переменных окружения HEROKU_API_KEY "
            "и HEROKU_APP_NAME, тогда команда заработает."
        )
        return

    parts = message.text.split(None, 2)
    if len(parts) < 3:
        await message.reply_text(
            "Использование: /setvar ключ значение\n\n"
            "Например: /setvar STREAM_URL http://radio.example.com/stream"
        )
        return

    key, value = parts[1], parts[2]
    try:
        Config.HEROKU_APP.config()[key] = value
        await message.reply_text(
            f"Готово, {key} теперь {value}.\n\nЧтобы применилось, перезапусти бота: /restart"
        )
    except Exception as e:
        await message.reply_text(f"Не получилось: {e}")


@bot.on_message(filters.command(["admins", "authusers"]) & admin_only())
async def cmd_admins(_, message: Message):
    """/admins — список дополнительных администраторов бота."""
    if not ADMINS:
        await message.reply_text(
            "Дополнительных администраторов из .env нет, команды доступны "
            "только администраторам чата и тем, кого добавили через панель."
        )
        return
    lines = [f"  {a}" for a in ADMINS]
    await message.reply_text("Администраторы из AUTH_USERS.\n\n" + "\n".join(lines))


# ══════════════════════════════════════════════════════════════════════════════
#  Баннер, картинка или видео вместо чёрного экрана во время звука
# ══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command(["banner"]) & admin_only())
async def cmd_banner(_, message: Message):
    """
    /banner ссылка               установить баннер по ссылке (картинка, гифка или видео)
    /banner (ответом на медиа)   установить из присланного фото, гифки или видео
    /banner pin                  закрепить баннер, чтобы треки его не перекрывали
    /banner unpin                открепить обратно
    /banner off                  убрать баннер
    /banner                      посмотреть текущее состояние
    """
    args  = message.command[1:]
    reply = message.reply_to_message

    if args and args[0].lower() in ("off", "none", "выкл", "убрать"):
        k = await message.reply_text("Убираю баннер...")
        await mp.set_banner(None)
        await k.edit("Готово, баннер убран, играет чистый звук.")
        return

    if args and args[0].lower() in ("pin", "закрепить", "пин"):
        if not Config.BANNER_URL:
            await message.reply_text("Сначала поставь баннер, потом можно закрепить его.")
            return
        await mp.set_banner(Config.BANNER_URL, pinned=True)
        await message.reply_text("Закрепил. Теперь треки не будут менять картинку на свою обложку.")
        return

    if args and args[0].lower() in ("unpin", "открепить", "анпин"):
        await mp.set_banner(Config.BANNER_URL, pinned=False)
        await message.reply_text("Открепил. YouTube-треки снова будут показывать свою обложку.")
        return

    media, ext = None, "jpg"
    if reply:
        if reply.photo:
            media, ext = reply.photo.file_id, "jpg"
        elif reply.animation:
            media, ext = reply.animation.file_id, "mp4"
        elif reply.video:
            media, ext = reply.video.file_id, "mp4"

    if media:
        k = await message.reply_text("Скачиваю и ставлю как баннер...")
        try:
            os.makedirs("downloads", exist_ok=True)
            path = await bot.download_media(media, file_name=f"downloads/banner.{ext}")
            await mp.set_banner(path)
            await k.edit("Готово, можешь посмотреть прямо сейчас.")
        except Exception as e:
            await k.edit(f"Не получилось: {e}")
        return

    if args:
        url = args[0]
        k = await message.reply_text("Ставлю баннер...")
        try:
            await mp.set_banner(url)
            await k.edit(f"Готово.\n{url}")
        except Exception as e:
            await k.edit(f"Не получилось: {e}")
        return

    current = Config.BANNER_URL
    if current:
        pin_note = "Он закреплён, треки его не перекрывают." if Config.BANNER_PINNED else "Он не закреплён, YouTube-треки будут показывать свою обложку вместо него."
        pin_hint = "Открепить: /banner unpin" if Config.BANNER_PINNED else "Закрепить: /banner pin"
        await message.reply_text(
            f"Текущий баннер:\n{current}\n\n{pin_note}\n\n"
            f"{pin_hint}\nУбрать: /banner off"
        )
    else:
        await message.reply_text(
            "Баннер пока не установлен, играет чистый звук без картинки.\n\n"
            "Как поставить: пришли ссылку командой /banner ссылка, "
            "или ответь на фото, гифку или видео командой /banner.\n\n"
            "У YouTube-треков своя обложка подставляется сама, даже без "
            "твоего баннера. Если хочешь, чтобы баннер всегда оставался "
            "одним и тем же, поставь его и закрепи командой /banner pin."
        )
