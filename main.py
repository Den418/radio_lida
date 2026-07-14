"""
╔══════════════════════════════════════════════════════════╗
║           RadioPlayerV3 — Точка входа (main.py)         ║
╠══════════════════════════════════════════════════════════╣
║  Порядок запуска:                                        ║
║  1. USER  — юзербот (войдёт в голосовой чат)            ║
║  2. call  — py-tgcalls поверх USER                      ║
║  3. bot   — Pyrogram-бот (принимает команды)            ║
║  4. Радио — сразу после старта                          ║
╚══════════════════════════════════════════════════════════╝

Запуск:
    python3 main.py
"""

# ═══════════════════════════════════════════════════════════════════════════
#  Проверяем ffmpeg и ffprobe ДО всего остального.
#
#  На своём компьютере они у тебя уже стоят, и эта строчка ничего не
#  трогает (weak=True значит "не лезь, если уже всё есть"). А вот на
#  сервере (Heroku, Railway и подобные) их часто нет и системный apt
#  недоступен — static-ffmpeg сам скачивает нужный бинарник при первом
#  запуске и добавляет в PATH, без доступа к системным пакетам.
# ═══════════════════════════════════════════════════════════════════════════
import static_ffmpeg
static_ffmpeg.add_paths(weak=True)

import asyncio

# ═══════════════════════════════════════════════════════════════════════════
#  КРИТИЧНО: создаём event loop ЗДЕСЬ, ДО импорта utils.py
#
#  Внутри utils.py есть строка `call = PyTgCalls(USER)`, а конструктор
#  PyTgCalls сам вызывает asyncio.get_event_loop() и запоминает результат.
#  Если к этому моменту loop ещё не создан явно, Python создаст свой,
#  "черновой" loop — а затем asyncio.run(main()) создал бы ЕЩЁ ОДИН,
#  СОВСЕМ ДРУГОЙ loop для запуска кода. Получается два разных loop'а:
#  один внутри call, другой — у которого реально работает всё остальное.
#  Отсюда ошибка "Future ... attached to a different loop".
#
#  Решение: создаём loop здесь и используем ИМЕННО его везде —
#  и для call, и для запуска main() внизу файла (loop.run_until_complete).
# ═══════════════════════════════════════════════════════════════════════════
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

import logging
import os

from pyrogram import filters, idle
from pyrogram.errors import UserAlreadyParticipant
from pyrogram.raw.functions.bots import SetBotCommands
from pyrogram.raw.types import BotCommand, BotCommandScopeDefault

from bot_client import bot
from config import Config
from utils import CHAT_ID, LOG_GROUP, ADMINS, call, mp, admin_filter
import utils

# ─── Логирование ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("RadioPlayerV3")

# Убираем лишний шум от сторонних библиотек
for _lib in ("pyrogram", "pytgcalls", "asyncio", "aiohttp"):
    logging.getLogger(_lib).setLevel(logging.WARNING)


# ── Меню команд в Telegram ────────────────────────────────────────────────────
BOT_COMMANDS = [
    ("start",       "🚀 Запустить бота / информация"),
    ("admin",       "🎛 Панель управления"),
    ("help",        "❓ Справка по командам"),
    ("play",        "🎵 Воспроизвести трек с YouTube"),
    ("playvideo",   "🎬 Воспроизвести видео (со звуком и картинкой)"),
    ("song",        "📥 Скачать аудио с YouTube"),
    ("skip",        "⏭ Пропустить текущий трек"),
    ("pause",       "⏸ Пауза"),
    ("resume",      "▶️ Продолжить воспроизведение"),
    ("radio",       "📻 Включить радио"),
    ("stopradio",   "⏹ Остановить радио"),
    ("current",     "🎶 Текущий трек"),
    ("playlist",    "📋 Очередь треков"),
    ("suggest",     "💡 Предложить трек или видео"),
    ("banner",      "🖼 Установить баннер (картинку)"),
    ("join",        "🔊 Войти в голосовой чат"),
    ("leave",       "🔇 Выйти из голосового чата"),
    ("mute",        "🔕 Заглушить юзербота"),
    ("unmute",      "🔔 Включить звук юзербота"),
    ("volume",      "🔊 Установить громкость (0-200)"),
    ("replay",      "🔁 Повторить трек сначала"),
    ("addadmin",    "👮 Добавить администратора"),
    ("removeadmin", "🚫 Удалить администратора"),
    ("clean",       "🗑 Удалить загруженные файлы"),
    ("restart",     "🔄 Обновить и перезапустить бота"),
    ("setvar",      "⚙️ Изменить Config Var (Heroku)"),
]


# ── Команда /restart ──────────────────────────────────────────────────────────
@bot.on_message(filters.command(["restart"]) & admin_filter)
async def cmd_restart(_, message):
    """/restart — обновить код и перезапустить (или рестартнуть Heroku dyno)."""
    k = await message.reply("🔄 **Перезапуск...**")

    is_heroku = await utils.trigger_restart()

    if is_heroku:
        await k.edit(
            "♻️ **Перезапускаю дино на Heroku...**\n"
            "_Бот вернётся через ~30 секунд._"
        )
    else:
        await k.edit("⬇️ **Обновляю код и перезапускаю...**\n_Подождите ~15 секунд._")


# ══════════════════════════════════════════════════════════════════════════════
#  Главная функция
#
#  ИСПРАВЛЕН баг оригинала:
#    Было: bot.run(main())  ← блокирует; весь код ниже никогда не выполняется
#          bot.start()       ← мёртвый код
#          idle()            ← мёртвый код
#
#  ИСПРАВЛЕН ВТОРОЙ баг (asyncio.run):
#    Было:  asyncio.run(main())              ← создаёт НОВЫЙ loop, не тот,
#                                                что уже сидит внутри call
#    Стало: loop.run_until_complete(main())  ← используем loop, созданный
#                                                в самом начале файла
# ══════════════════════════════════════════════════════════════════════════════
async def main():
    from user import USER

    # 1. Запускаем юзербота
    log.info("Запускаем юзербота...")
    await USER.start()
    user_me = await USER.get_me()
    log.info("✅ Юзербот: %s (%s)", user_me.first_name, user_me.id)

    # 2. Запускаем py-tgcalls (после юзербота)
    log.info("Запускаем py-tgcalls...")
    await call.start()
    log.info("✅ py-tgcalls запущен")

    # 3. Запускаем бота
    log.info("Запускаем бота...")
    await bot.start()
    bot_me = await bot.get_me()
    utils.USERNAME = bot_me.username
    log.info("✅ Бот: @%s", bot_me.username)

    # Устанавливаем меню команд
    try:
        await bot.invoke(SetBotCommands(
            scope=BotCommandScopeDefault(),
            lang_code="ru",
            commands=[BotCommand(command=c, description=d) for c, d in BOT_COMMANDS],
        ))
    except Exception as e:
        log.warning("Меню команд: %s", e)

    # 4. Уведомляем лог-группу
    if LOG_GROUP:
        try:
            await bot.send_message(
                LOG_GROUP,
                f"«{Config.RADIO_NAME}» запущено.\n\n"
                f"Бот: @{bot_me.username}\n"
                f"Юзербот: {user_me.first_name} ({user_me.id})\n"
                f"Чат: {CHAT_ID}\n"
                f"Радио: {Config.STREAM_URL}",
                disable_web_page_preview=True,
            )
        except Exception as e:
            log.warning("Стартовое сообщение в лог: %s", e)

    # 5. Запускаем радио
    log.info("Запускаем радио...")
    try:
        await mp.start_radio()
    except Exception as e:
        log.error("Не удалось запустить радио: %s", e)
        log.error("Проверь CHAT_ID и что юзербот — участник чата")

    print("\n" + "═" * 50)
    print(f"  «{Config.RADIO_NAME}» работает!")
    print(f"  Бот:   @{bot_me.username}")
    print(f"  Чат:   {CHAT_ID}")
    print(f"  Ctrl+C для остановки")
    print("═" * 50 + "\n")

    # Держим процесс живым
    await idle()

    # Завершение (Ctrl+C или SIGTERM)
    log.info("Останавливаем...")
    await mp.stop_radio()
    await bot.stop()
    await USER.stop()
    log.info("Бот остановлен.")


if __name__ == "__main__":
    loop.run_until_complete(main())
