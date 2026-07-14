"""
Плагин: /start и /help

Ведут себя по-разному в зависимости от того, кто пишет.
Админ бота видит панель управления и полную справку.
Кто угодно ещё видит короткое сообщение с контактом поддержки и
подсказкой про /suggest — единственное, что доступно всем.
"""
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from bot_client import bot
from config import Config
from utils import mp, CHAT_ID, admin_filter

# ── Сообщение для не-админов ────────────────────────────────────────────────
NON_ADMIN_TEXT = (
    f"Этот бот управляет радио «{Config.RADIO_NAME}» и не предназначен для "
    f"обычных слушателей.\n\n"
    f"Если хочешь предложить трек или видео для эфира, напиши /suggest и "
    f"название, или ссылку. По остальным вопросам пиши в поддержку: "
    f"{Config.SUPPORT_CONTACT}"
)

HELP_TEXT = f"""
Справка по командам «{Config.RADIO_NAME}»

Открой /admin, там всё то же самое, только кнопками, обычно так удобнее.

Музыка
/play ссылка или название — добавить трек с YouTube
/playvideo ссылка или название — добавить видео со звуком и картинкой
/song ссылка или название — скачать аудио и добавить файлом
/skip, /pause, /resume, /replay — управление воспроизведением
/current, /playlist — что играет и что в очереди

Просто кинь боту в личку, или в служебный чат, если он настроен, аудиофайл
или голосовое, он сам добавит его в очередь, без команд.

Радио
/radio — включить радио-поток
/stopradio — остановить и выйти из голосового чата

Баннер, картинка вместо чёрного экрана
/banner ссылка — поставить баннер
/banner, ответом на фото, гифку или видео — поставить из присланного
/banner pin, /banner unpin — закрепить, чтобы треки его не перекрывали
/banner off — убрать

Голосовой чат
/join, /leave — войти и выйти
/mute, /unmute — звук юзербота
/volume 0-200 — громкость, 100 обычная

Предложения от слушателей
Обычные пользователи предлагают треки командой /suggest, ты увидишь их
в /admin в разделе «Предложения» и решишь, принять или отклонить.

Админы
/addadmin id или @username — добавить
/removeadmin id — убрать, только тех, кто добавлен через панель

Обслуживание
/clean — удалить загруженные файлы
/restart — обновить бота с GitHub и перезапустить
/setvar ключ значение — изменить переменную на Heroku
"""


@bot.on_message(filters.command(["start"]))
async def cmd_start(_, message: Message):
    """Приветствие, разное для админов и обычных пользователей."""
    if not message.from_user:
        return

    admins = await mp.get_admins(CHAT_ID)
    is_admin = message.from_user.id in admins

    if not is_admin:
        await message.reply_text(NON_ADMIN_TEXT)
        return

    name = message.from_user.first_name
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎛 Открыть панель управления", callback_data="pnl:main")],
        [InlineKeyboardButton("❓ Полная справка", callback_data="show_help")],
    ])
    await message.reply_text(
        f"Привет, {name}.\n\n"
        f"Это центр управления «{Config.RADIO_NAME}». Отсюда можно "
        f"управлять воспроизведением, очередью, баннером, предложениями "
        f"слушателей и админами бота.\n\n"
        f"Нажми «Открыть панель управления», чтобы начать.",
        reply_markup=keyboard,
    )


@bot.on_message(filters.command(["help"]))
async def cmd_help(_, message: Message):
    """Справка по всем командам, только для админов."""
    if not message.from_user:
        return

    admins = await mp.get_admins(CHAT_ID)
    if message.from_user.id not in admins:
        await message.reply_text(NON_ADMIN_TEXT)
        return

    await message.reply_text(HELP_TEXT, disable_web_page_preview=True)


@bot.on_callback_query(filters.regex("^show_help$") & admin_filter)
async def cb_show_help(_, query):
    """Кнопка «Полная справка» в стартовом сообщении."""
    await query.message.edit_text(HELP_TEXT, disable_web_page_preview=True)
    await query.answer()
