"""
Плагин: Панель управления (/admin)

Кликабельная панель вместо запоминания команд: воспроизведение,
очередь, баннер, предложения от слушателей, админы, статистика.

Всё живёт в одном сообщении, кнопки просто переключают экраны.
"""
import time

from pyrogram import filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from bot_client import bot
from config import Config
from utils import ADMINS, CHAT_ID, call, mp, playlist, suggestions, admin_filter, Stats


# ══════════════════════════════════════════════════════════════════════════════
#  Отрисовка экрана: правит одно и то же сообщение, не падает на
#  MESSAGE_NOT_MODIFIED (когда нажали кнопку, а содержимое не изменилось),
#  и всегда отвечает на callback, чтобы кнопка не крутилась вечно.
# ══════════════════════════════════════════════════════════════════════════════
async def _render(query: CallbackQuery, text: str, kb: InlineKeyboardMarkup, toast: str | None = None):
    try:
        await query.message.edit_text(text, reply_markup=kb)
    except MessageNotModified:
        pass
    except Exception as e:
        try:
            await query.answer(f"Ошибка: {e}", show_alert=True)
        except Exception:
            pass
        return
    try:
        await query.answer(toast) if toast else await query.answer()
    except Exception:
        pass


def _format_uptime(seconds: float) -> str:
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days} д")
    if hours:
        parts.append(f"{hours} ч")
    if minutes:
        parts.append(f"{minutes} м")
    if not parts:
        parts.append(f"{seconds} с")
    return " ".join(parts)


def _status_line() -> str:
    if playlist:
        song = playlist[0]
        icon = "🎬" if song[3] in ("video", "telegram_video") else "🎵"
        rest = len(playlist) - 1
        extra = f", и ещё {rest} в очереди" if rest else ""
        return f"{icon} Играет {song[1]}{extra}"
    pause_note = ", но сейчас на паузе" if Stats.is_paused else ""
    return f"📻 Играет радио {Config.RADIO_NAME}{pause_note}"


# ══════════════════════════════════════════════════════════════════════════════
#  Экраны панели, каждый возвращает (текст, клавиатура)
# ══════════════════════════════════════════════════════════════════════════════

def _main_screen():
    text = f"Панель «{Config.RADIO_NAME}»\n\n{_status_line()}"

    sug_label = f"💡 Предложения ({len(suggestions)})" if suggestions else "💡 Предложения"

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ Играть", callback_data="pnl:play"),
            InlineKeyboardButton("⏸ Пауза", callback_data="pnl:pause"),
        ],
        [
            InlineKeyboardButton("⏭ Пропустить", callback_data="pnl:skip"),
            InlineKeyboardButton("⏹ Стоп", callback_data="pnl:stop"),
        ],
        [
            InlineKeyboardButton("📻 Радио", callback_data="pnl:radio"),
            InlineKeyboardButton(sug_label, callback_data="pnl:suggestions"),
        ],
        [
            InlineKeyboardButton("📋 Очередь", callback_data="pnl:queue"),
            InlineKeyboardButton(f"🔊 Громкость {Stats.volume}%", callback_data="pnl:vol"),
        ],
        [
            InlineKeyboardButton("🖼 Баннер", callback_data="pnl:banner"),
            InlineKeyboardButton("👮 Админы", callback_data="pnl:admins"),
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data="pnl:stats"),
            InlineKeyboardButton("🔄 Обновить", callback_data="pnl:main"),
        ],
        [InlineKeyboardButton("🔄 Перезапуск бота", callback_data="pnl:restart")],
        [InlineKeyboardButton("✖️ Закрыть", callback_data="pnl:close")],
    ])
    return text, kb


def _queue_screen():
    if not playlist:
        text = "Очередь пуста, сейчас играет радио."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="pnl:main")]])
        return text, kb

    lines = [f"{i}. {x[1]}, запросил {x[4]}" for i, x in enumerate(playlist, 1)]
    text = "Очередь треков.\n\n" + "\n".join(lines)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Очистить очередь", callback_data="pnl:queue:clear")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="pnl:main")],
    ])
    return text, kb


def _volume_screen():
    filled = Stats.volume // 10
    bar = "▓" * filled + "░" * (20 - filled)
    text = f"Громкость сейчас {Stats.volume} процентов.\n{bar}"

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➖ 10", callback_data="pnl:vol:down"),
            InlineKeyboardButton("➕ 10", callback_data="pnl:vol:up"),
        ],
        [
            InlineKeyboardButton("🔉 50%", callback_data="pnl:vol:50"),
            InlineKeyboardButton("🔊 100%", callback_data="pnl:vol:100"),
            InlineKeyboardButton("📢 150%", callback_data="pnl:vol:150"),
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data="pnl:main")],
    ])
    return text, kb


def _banner_screen():
    current = Config.BANNER_URL
    if current:
        if Config.BANNER_PINNED:
            status = "Закреплён, треки не будут менять картинку на свою обложку."
            pin_label, pin_data = "📌 Открепить", "pnl:banner:unpin"
        else:
            status = "Не закреплён, YouTube-треки будут показывать свою обложку вместо него."
            pin_label, pin_data = "📌 Закрепить", "pnl:banner:pin"
        text = f"Текущий баннер:\n{current}\n\n{status}"
        rows = [
            [InlineKeyboardButton(pin_label, callback_data=pin_data)],
            [InlineKeyboardButton("🗑 Убрать баннер", callback_data="pnl:banner:clear")],
        ]
    else:
        text = (
            "Баннер пока не установлен, играет чистый звук без картинки.\n\n"
            "Поставить можно командой /banner ссылка, или ответом на фото, "
            "гифку или видео с подписью /banner."
        )
        rows = []
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="pnl:main")])
    return text, InlineKeyboardMarkup(rows)


async def _admins_screen():
    static  = ADMINS
    dynamic = Config.DYNAMIC_ADMINS

    lines = ["Администраторы бота.\n"]
    if static:
        lines.append("Из .env, менять можно только вручную:")
        lines.extend(f"  {a}" for a in static)
        lines.append("")
    lines.append("Добавлены через панель:")
    if dynamic:
        lines.extend(f"  {a}" for a in dynamic)
    else:
        lines.append("  пока никого нет")
    lines.append("")
    lines.append("Добавить: /addadmin, укажи id или @username.")
    lines.append("Можно и ответом на сообщение человека с подписью /addadmin.")

    text = "\n".join(lines)

    rows = [
        [InlineKeyboardButton(f"❌ Убрать {a}", callback_data=f"pnl:admins:rm:{a}")]
        for a in dynamic
    ]
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="pnl:main")])
    return text, InlineKeyboardMarkup(rows)


def _suggestions_screen():
    if not suggestions:
        text = "Предложений пока нет."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="pnl:main")]])
        return text, kb

    lines = ["Вот что предлагают послушать.\n"]
    rows = []
    for item in suggestions:
        icon = "🎬" if item["src_type"] in ("video", "telegram_video") else "🎵"
        lines.append(f"{icon} {item['title']}, от {item['by_mention']}")
        short_title = item["title"][:22]
        rows.append([
            InlineKeyboardButton(f"✅ {short_title}", callback_data=f"pnl:sug:ok:{item['id']}"),
            InlineKeyboardButton("❌", callback_data=f"pnl:sug:no:{item['id']}"),
        ])
    text = "\n".join(lines)
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="pnl:main")])
    return text, InlineKeyboardMarkup(rows)


async def _stats_screen():
    uptime = _format_uptime(time.time() - Stats.start_time)
    admins = await mp.get_admins(CHAT_ID)

    history = "\n".join(f"  {t}" for t in list(Stats.history)[:5]) or "  пока пусто"
    top = Stats.requesters.most_common(5)
    top_lines = "\n".join(f"  {name}, {n}" for name, n in top) or "  пока пусто"

    text = (
        f"Статистика «{Config.RADIO_NAME}».\n\n"
        f"Бот работает {uptime}.\n"
        f"Треков сыграно за это время: {Stats.tracks_played}.\n"
        f"Сейчас в очереди: {len(playlist)}.\n"
        f"Предложений ждут решения: {len(suggestions)}.\n"
        f"Админов бота: {len(admins)}.\n\n"
        f"Последнее, что играло:\n{history}\n\n"
        f"Кто чаще всего заказывает треки:\n{top_lines}"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="pnl:main")]])
    return text, kb


def _restart_confirm_screen():
    text = "Точно перезапустить бота? Вернётся примерно через пятнадцать-тридцать секунд."
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да, перезапустить", callback_data="pnl:restart:go")],
        [InlineKeyboardButton("❌ Отмена", callback_data="pnl:main")],
    ])
    return text, kb


# ══════════════════════════════════════════════════════════════════════════════
#  Команда открытия панели
# ══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command(["admin", "panel"]) & admin_filter)
async def cmd_admin_panel(_, message: Message):
    """/admin — открыть панель управления."""
    text, kb = _main_screen()
    await message.reply_text(text, reply_markup=kb)


# ══════════════════════════════════════════════════════════════════════════════
#  Диспетчер кнопок панели
# ══════════════════════════════════════════════════════════════════════════════

@bot.on_callback_query(filters.regex(r"^pnl:") & admin_filter)
async def panel_callback(client, query: CallbackQuery):
    data = query.data

    if data == "pnl:main":
        text, kb = _main_screen()
        await _render(query, text, kb)

    elif data == "pnl:play":
        try:
            if Stats.is_paused:
                await call.resume(CHAT_ID)
                Stats.is_paused = False
            elif playlist:
                await mp.play_song(playlist[0])
            else:
                await mp.start_radio()
        except Exception as e:
            await query.answer(f"Не получилось: {e}", show_alert=True)
            return
        text, kb = _main_screen()
        await _render(query, text, kb, "Играет")

    elif data == "pnl:pause":
        try:
            await call.pause(CHAT_ID)
            Stats.is_paused = True
        except Exception as e:
            await query.answer(f"Не получилось: {e}", show_alert=True)
            return
        text, kb = _main_screen()
        await _render(query, text, kb, "Пауза")

    elif data == "pnl:skip":
        await mp.skip_current_playing()
        text, kb = _main_screen()
        await _render(query, text, kb, "Пропустил")

    elif data == "pnl:stop":
        await mp.stop_radio()
        text, kb = _main_screen()
        await _render(query, text, kb, "Остановил")

    elif data == "pnl:radio":
        await mp.start_radio()
        text, kb = _main_screen()
        await _render(query, text, kb, "Включил радио")

    elif data == "pnl:queue":
        text, kb = _queue_screen()
        await _render(query, text, kb)

    elif data == "pnl:queue:clear":
        playlist.clear()
        text, kb = _queue_screen()
        await _render(query, text, kb, "Очередь очищена")

    elif data == "pnl:vol":
        text, kb = _volume_screen()
        await _render(query, text, kb)

    elif data.startswith("pnl:vol:"):
        action = data.rsplit(":", 1)[1]
        if action == "up":
            Stats.volume = min(200, Stats.volume + 10)
        elif action == "down":
            Stats.volume = max(0, Stats.volume - 10)
        else:
            Stats.volume = int(action)
        try:
            await call.change_volume_call(CHAT_ID, Stats.volume)
        except Exception as e:
            await query.answer(f"Не получилось: {e}", show_alert=True)
            return
        text, kb = _volume_screen()
        await _render(query, text, kb)

    elif data == "pnl:banner":
        text, kb = _banner_screen()
        await _render(query, text, kb)

    elif data == "pnl:banner:clear":
        await mp.set_banner(None)
        text, kb = _banner_screen()
        await _render(query, text, kb, "Баннер убран")

    elif data == "pnl:banner:pin":
        await mp.set_banner(Config.BANNER_URL, pinned=True)
        text, kb = _banner_screen()
        await _render(query, text, kb, "Закреплён")

    elif data == "pnl:banner:unpin":
        await mp.set_banner(Config.BANNER_URL, pinned=False)
        text, kb = _banner_screen()
        await _render(query, text, kb, "Откреплён")

    elif data == "pnl:admins":
        text, kb = await _admins_screen()
        await _render(query, text, kb)

    elif data.startswith("pnl:admins:rm:"):
        target = int(data.rsplit(":", 1)[1])
        ok = await mp.remove_admin(target)
        text, kb = await _admins_screen()
        await _render(query, text, kb, "Удалён" if ok else "Не нашёл")

    elif data == "pnl:suggestions":
        text, kb = _suggestions_screen()
        await _render(query, text, kb)

    elif data.startswith("pnl:sug:ok:"):
        sug_id = int(data.rsplit(":", 1)[1])
        item = await mp.approve_suggestion(sug_id)
        if item:
            try:
                await client.send_message(
                    item["by_id"],
                    f"Твоё предложение приняли, скоро будет в эфире: {item['title']}",
                )
            except Exception:
                pass
        text, kb = _suggestions_screen()
        await _render(query, text, kb, "Принято" if item else "Уже не актуально")

    elif data.startswith("pnl:sug:no:"):
        sug_id = int(data.rsplit(":", 1)[1])
        item = mp.reject_suggestion(sug_id)
        if item:
            try:
                await client.send_message(
                    item["by_id"],
                    f"Предложение не подошло в этот раз: {item['title']}",
                )
            except Exception:
                pass
        text, kb = _suggestions_screen()
        await _render(query, text, kb, "Отклонено" if item else "Уже не актуально")

    elif data == "pnl:stats":
        text, kb = await _stats_screen()
        await _render(query, text, kb)

    elif data == "pnl:restart":
        text, kb = _restart_confirm_screen()
        await _render(query, text, kb)

    elif data == "pnl:restart:go":
        from utils import trigger_restart
        try:
            await query.message.edit_text("Перезапускаюсь, вернусь через пятнадцать-тридцать секунд.")
        except MessageNotModified:
            pass
        await query.answer()
        await trigger_restart()

    elif data == "pnl:close":
        await query.message.delete()
        await query.answer()

    else:
        await query.answer()


# ══════════════════════════════════════════════════════════════════════════════
#  Добавление и удаление админов текстовыми командами
#  (нужны отдельно от панели, кнопка не может принять произвольный id)
# ══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command(["addadmin"]) & admin_filter)
async def cmd_addadmin(client, message: Message):
    """
    /addadmin id_или_@username   добавить администратора бота
    Или ответь этой командой на сообщение человека.
    """
    reply = message.reply_to_message
    target_id = None
    target_name = None

    if reply and reply.from_user:
        target_id = reply.from_user.id
        target_name = reply.from_user.mention
    else:
        args = message.command[1:]
        if not args:
            await message.reply_text(
                "Укажи id или @username.\n\n"
                "Например:\n"
                "/addadmin 123456789\n"
                "/addadmin @username\n"
                "Или ответь на сообщение человека командой /addadmin"
            )
            return
        arg = args[0].lstrip("@")
        if arg.isdigit():
            target_id = int(arg)
            target_name = f"{target_id}"
        else:
            try:
                user = await client.get_users(arg)
                target_id = user.id
                target_name = user.mention
            except Exception:
                await message.reply_text(f"Не нашёл пользователя @{arg}.")
                return

    ok = await mp.add_admin(target_id)
    if ok:
        await message.reply_text(f"Готово, {target_name} теперь администратор бота.")
    else:
        await message.reply_text(f"{target_name} уже администратор.")


@bot.on_message(filters.command(["removeadmin", "deladmin"]) & admin_filter)
async def cmd_removeadmin(_, message: Message):
    """/removeadmin id — убрать администратора, добавленного через панель."""
    reply = message.reply_to_message
    target_id = None

    if reply and reply.from_user:
        target_id = reply.from_user.id
    else:
        args = message.command[1:]
        if not args or not args[0].lstrip("-").isdigit():
            await message.reply_text(
                "Укажи id администратора.\n\n"
                "Например: /removeadmin 123456789\n\n"
                "Посмотреть список можно в /admin, раздел «Админы»."
            )
            return
        target_id = int(args[0])

    ok = await mp.remove_admin(target_id)
    if ok:
        await message.reply_text(f"Готово, админ {target_id} удалён.")
    else:
        await message.reply_text(
            f"Не могу удалить {target_id}, он не был добавлен через панель. "
            f"Возможно, это админ из .env или админ чата, их меняют вручную."
        )
