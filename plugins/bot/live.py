"""
Плагин: Живой эфир — трансляция микрофона (или любого звука с ПК) в чат

Как это работает:
  Юзербот умеет транслировать в голосовой чат звук с любого аудио-устройства
  машины, на которой запущен main.py. Это может быть:
  • Обычный микрофон — говоришь, тебя слышно как живого ведущего радио
  • Виртуальный аудио-кабель (VB-Audio Virtual Cable, VoiceMeeter и т.п.) —
    так можно транслировать звук ЛЮБОЙ программы на компьютере
    (Spotify, браузер, любой плеер) — не только голос с микрофона

ВАЖНО: работает, только если main.py запущен на машине с реальным
аудио-устройством (обычный компьютер). На "голом" сервере/VPS без
звуковой карты эта функция технически недоступна — там физически
нет микрофона, который можно было бы захватить.
"""
from pyrogram import filters
from pyrogram.types import Message

from bot_client import bot
from utils import mp, admin_filter


@bot.on_message(filters.command(["mics", "devices"]) & admin_filter)
async def cmd_mics(_, message: Message):
    """/mics — список доступных аудио-устройств на машине, где работает бот."""
    from pytgcalls.media_devices import MediaDevices

    try:
        mics = MediaDevices.microphone_devices()
    except Exception as e:
        await message.reply_text(
            f"❌ Не удалось получить список устройств:\n`{e}`\n\n"
            f"Скорее всего, бот работает на сервере без звуковой карты — "
            f"живой эфир там физически невозможен. Эта функция работает, "
            f"только если бот запущен на обычном компьютере."
        )
        return

    if not mics:
        await message.reply_text(
            "🎤 Аудио-устройств не найдено.\n\n"
            "Убедись, что к компьютеру, на котором запущен бот, подключён "
            "микрофон (или установлен виртуальный аудио-кабель типа "
            "VB-Audio Virtual Cable)."
        )
        return

    lines = [f"`{i}.` {m.title}" for i, m in enumerate(mics)]
    await message.reply_text(
        "🎤 **Доступные устройства:**\n\n" + "\n".join(lines) +
        "\n\n_Запустить эфир: `/live 0` (или другой номер из списка)_"
    )


@bot.on_message(filters.command(["live"]) & admin_filter)
async def cmd_live(_, message: Message):
    """/live [номер] — начать живой эфир с выбранного устройства (по умолчанию — 0)."""
    args = message.command[1:]
    index = 0
    if args:
        if not args[0].isdigit():
            await message.reply_text("❌ Номер устройства должен быть числом.\nСписок: /mics")
            return
        index = int(args[0])

    k = await message.reply_text("🎙 Подключаюсь к устройству...")
    try:
        await mp.go_live(index)
        await k.edit(
            "🔴 **В ЭФИРЕ!**\n\n"
            "Всё, что звучит на выбранном устройстве, слышно в голосовом чате прямо сейчас.\n"
            "Закончить: /stoplive"
        )
    except IndexError as e:
        await k.edit(f"❌ Такого устройства нет: {e}\n\nСписок: /mics")
    except RuntimeError as e:
        await k.edit(f"❌ {e}\n\nПроверь /mics — возможно, бот работает на сервере без звуковой карты.")
    except Exception as e:
        await k.edit(f"❌ Не удалось начать эфир: `{e}`")


@bot.on_message(filters.command(["stoplive", "offline"]) & admin_filter)
async def cmd_stoplive(_, message: Message):
    """/stoplive — закончить живой эфир, вернуться к радио/очереди."""
    if not mp.is_live:
        await message.reply_text("ℹ️ Живой эфир сейчас не идёт.")
        return
    k = await message.reply_text("⏹ Завершаю эфир...")
    await mp.stop_live()
    await k.edit("✅ Эфир завершён. Возвращаюсь к радио/очереди.")
