"""
╔══════════════════════════════════════════════════════════╗
║              RadioPlayerV3 — Ядро (utils.py)            ║
║                                                          ║
║  Написано под py-tgcalls 2.x (пакет py-tgcalls)        ║
╚══════════════════════════════════════════════════════════╝

Формат элемента плейлиста (Config.playlist):
  [0] msg_id    — ID сообщения с запросом
  [1] title     — Название трека
  [2] source    — YouTube URL, file_id Telegram-файла или прямая ссылка
  [3] src_type  — "youtube" | "telegram" | "direct" | "video" | "telegram_video"
  [4] by        — Кто запросил (mention пользователя)
  [5] thumbnail — Картинка-обложка для показа как "видео" (или None)

Предложения от пользователей (suggestions) — отдельный список словарей,
ждут решения администратора в панели, не играют сами по себе.
"""
import asyncio
import logging
import os
import time
from asyncio import sleep
from collections import Counter, deque
from random import randint

from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.raw.functions.phone import CreateGroupCall, EditGroupCallTitle
from pyrogram.raw.functions.channels import GetFullChannel
from pyrogram.raw.types import InputGroupCall

from pytgcalls import PyTgCalls
from pytgcalls.types import (
    MediaStream,
    AudioQuality,
    VideoQuality,
    StreamEnded,
    ChatUpdate,
    Update,
)

from config import Config
from user import USER
from bot_client import bot

log = logging.getLogger(__name__)

# ─── Локальные копии настроек ─────────────────────────────────────────────────
CHAT_ID        = Config.CHAT_ID
STREAM_URL     = Config.STREAM_URL
DURATION_LIMIT = Config.DURATION_LIMIT
LOG_GROUP      = Config.LOG_GROUP
DELAY          = Config.DELAY
EDIT_TITLE     = Config.EDIT_TITLE
RADIO_TITLE    = Config.RADIO_TITLE
ADMINS         = Config.ADMINS

# ─── Общее изменяемое состояние ───────────────────────────────────────────────
playlist = Config.playlist   # Очередь треков (общий объект с Config)
msg      = Config.msg        # Служебные сообщения

ADMIN_LIST: dict = {}        # Кэш администраторов (сбрасывается при add/remove_admin)
USERNAME = ""                # Устанавливается в main.py после старта бота

# ─── Предложения от пользователей ──────────────────────────────────────────────
# Список словарей: {id, title, source, src_type, thumbnail, by_mention, by_id}
# id — свой счётчик, а не индекс в списке, чтобы кнопки не путались,
# если несколько предложений обработали не по порядку.
suggestions: list = []
_next_suggestion_id = [1]
SUGGESTIONS_PER_USER_LIMIT = 3   # чтобы никто не мог завалить очередь спамом

# ─── Статистика (сбрасывается при перезапуске бота) ───────────────────────────
class Stats:
    start_time     = time.time()   # Когда запустился бот
    tracks_played  = 0             # Сколько треков сыграно за сессию
    requesters     = Counter()     # Кто сколько треков заказал (mention -> счётчик)
    volume         = 100           # Текущая громкость (для отображения в панели)
    is_paused      = False         # Стоит ли воспроизведение на паузе
    history        = deque(maxlen=10)   # Последние сыгранные треки (для статистики)

# ─── Параметры yt-dlp для разных режимов ──────────────────────────────────────
_YTDLP_AUDIO = "--format bestaudio[ext=m4a]/bestaudio/best"
_YTDLP_VIDEO = "--format bestvideo[height<=720]+bestaudio/best/best"

# Если баннер похож на гифку или видео — просим ffmpeg крутить его по кругу,
# пока играет звук (обычные картинки library и так зацикливает сама).
_LOOPABLE_BANNER_EXT = (".mp4", ".mov", ".webm", ".mkv", ".gif", ".m4v", ".avi")

# ─── PyTgCalls — главный объект голосовых чатов ───────────────────────────────
call = PyTgCalls(USER)


# ══════════════════════════════════════════════════════════════════════════════
#  Поиск на YouTube — общая функция для /play, /playvideo, /suggest
# ══════════════════════════════════════════════════════════════════════════════
async def youtube_lookup(query: str) -> dict | None:
    """Найти трек или видео на YouTube (или по прямой ссылке), вернуть метаданные."""
    from yt_dlp import YoutubeDL

    opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "default_search": "ytsearch1",
        "geo-bypass": True,
        "nocheckcertificate": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                info = info["entries"][0]
            return info
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  MusicPlayer — управление воспроизведением
# ══════════════════════════════════════════════════════════════════════════════
class MusicPlayer:

    # ── Отображение плейлиста ─────────────────────────────────────────────────

    async def send_playlist(self):
        """Обновить сообщение с очередью треков в лог-группе."""
        if not LOG_GROUP:
            return

        if not playlist:
            text = "Очередь пуста, играет радио."
        else:
            lines = [
                f"{i}. {x[1]}, запросил {x[4]}"
                for i, x in enumerate(playlist, 1)
            ]
            text = "Очередь треков:\n\n" + "\n".join(lines)

        if msg.get("playlist"):
            try:
                await msg["playlist"].delete()
            except Exception:
                pass
            msg["playlist"] = None

        try:
            msg["playlist"] = await bot.send_message(
                LOG_GROUP, text,
                disable_web_page_preview=True,
                disable_notification=True,
            )
        except FloodWait as e:
            await sleep(e.value)
        except Exception as e:
            log.warning("send_playlist: %s", e)

    # ── Добавление в очередь ──────────────────────────────────────────────────

    async def add_to_queue(self, song: list) -> int:
        """
        Добавить трек в очередь. Если очередь была пуста — сразу начинаем
        играть. Возвращает позицию трека, считая с 1.
        """
        playlist.append(song)
        pos = len(playlist)
        if pos == 1:
            await self.play_song(playlist[0])
        return pos

    # ── Предложения от пользователей ───────────────────────────────────────────

    def add_suggestion(self, title, source, src_type, user, thumbnail=None) -> dict | None:
        """
        Добавить предложение в очередь на рассмотрение. None, если у этого
        человека уже висит слишком много предложений без ответа.
        """
        pending = sum(1 for s in suggestions if s["by_id"] == user.id)
        if pending >= SUGGESTIONS_PER_USER_LIMIT:
            return None

        item = {
            "id": _next_suggestion_id[0],
            "title": title,
            "source": source,
            "src_type": src_type,
            "thumbnail": thumbnail,
            "by_mention": user.mention,
            "by_id": user.id,
        }
        _next_suggestion_id[0] += 1
        suggestions.append(item)
        return item

    async def approve_suggestion(self, sug_id: int) -> dict | None:
        """Принять предложение — переносит его в настоящую очередь."""
        for i, item in enumerate(suggestions):
            if item["id"] == sug_id:
                suggestions.pop(i)
                song = [0, item["title"], item["source"], item["src_type"],
                        item["by_mention"], item["thumbnail"]]
                await self.add_to_queue(song)
                return item
        return None

    def reject_suggestion(self, sug_id: int) -> dict | None:
        """Отклонить предложение."""
        for i, item in enumerate(suggestions):
            if item["id"] == sug_id:
                return suggestions.pop(i)
        return None

    # ── Сборка потока (аудио [+ баннер] или видео) ────────────────────────────

    @staticmethod
    def _banner_ffmpeg_params(banner: str) -> str | None:
        """Если баннер похож на гифку/видео — просим ffmpeg зациклить его."""
        path_only = banner.split("?", 1)[0].lower()
        if path_only.endswith(_LOOPABLE_BANNER_EXT):
            return "--video --start -stream_loop -1"
        return None

    def _make_stream(
        self,
        audio_source: str,
        banner: str | None = None,
        ytdlp_parameters: str | None = None,
    ) -> MediaStream:
        """
        Собрать MediaStream для аудио-трека. Если задан banner — показываем
        его вместо чёрного экрана (картинка, гифка или видео).
        """
        if banner:
            return MediaStream(
                banner,
                audio_path=audio_source,
                audio_parameters=AudioQuality.HIGH,
                video_parameters=VideoQuality.SD_480p,
                ytdlp_parameters=ytdlp_parameters,
                ffmpeg_parameters=self._banner_ffmpeg_params(banner),
            )
        return MediaStream(
            audio_source,
            audio_parameters=AudioQuality.HIGH,
            video_flags=MediaStream.Flags.IGNORE,
            ytdlp_parameters=ytdlp_parameters,
        )

    def _make_video_stream(
        self,
        video_source: str,
        ytdlp_parameters: str | None = None,
    ) -> MediaStream:
        """Собрать MediaStream для настоящего видео (звук и картинка из одного источника)."""
        return MediaStream(
            video_source,
            audio_parameters=AudioQuality.HIGH,
            video_parameters=VideoQuality.HD_720p,
            ytdlp_parameters=ytdlp_parameters,
        )

    def _effective_banner(self, thumbnail: str | None) -> str | None:
        """
        Какую картинку показывать: если баннер закреплён — только его,
        трек тут ни при чём. Иначе — сперва обложка трека, потом баннер.
        """
        if Config.BANNER_PINNED and Config.BANNER_URL:
            return Config.BANNER_URL
        return thumbnail or Config.BANNER_URL

    # ── Воспроизведение ───────────────────────────────────────────────────────

    async def start_radio(self):
        """Запустить радио-поток (STREAM_URL), с баннером если он задан."""
        playlist.clear()
        log.info("Запускаем радио: %s", STREAM_URL)

        stream = self._make_stream(STREAM_URL, Config.BANNER_URL)

        try:
            await call.play(CHAT_ID, stream)
        except Exception as e:
            log.error("play() не удался (%s), пробуем создать голосовой чат", e)
            await self._create_voice_chat()
            await call.play(CHAT_ID, stream)

        if EDIT_TITLE and RADIO_TITLE:
            await self.edit_title(RADIO_TITLE)

        Stats.is_paused = False
        log.info("Радио запущено")

    async def stop_radio(self):
        """Остановить воспроизведение и покинуть голосовой чат."""
        playlist.clear()
        try:
            await call.leave_call(CHAT_ID)
            log.info("Вышли из голосового чата")
        except Exception as e:
            log.warning("leave_call: %s", e)

    async def play_song(self, song: list):
        """Начать воспроизведение трека из плейлиста."""
        src_type: str = song[3]
        src: str      = song[2]
        thumb         = song[5] if len(song) > 5 else None
        banner        = self._effective_banner(thumb)

        if src_type == "video":
            stream = self._make_video_stream(src, ytdlp_parameters=_YTDLP_VIDEO)

        elif src_type == "telegram_video":
            file_path = await self._download_telegram(song, ext="mp4")
            if not file_path:
                await self._skip_broken(song)
                return
            stream = self._make_video_stream(file_path)

        elif src_type == "youtube":
            stream = self._make_stream(src, banner, ytdlp_parameters=_YTDLP_AUDIO)

        elif src_type == "telegram":
            file_path = await self._download_telegram(song, ext="m4a")
            if not file_path:
                await self._skip_broken(song)
                return
            stream = self._make_stream(file_path, banner)

        else:
            stream = self._make_stream(src, banner)

        try:
            await call.play(CHAT_ID, stream)
        except Exception as e:
            log.error("play_song — play(): %s", e)
            await self._skip_broken(song)
            return

        if EDIT_TITLE:
            icon = "🎬" if src_type in ("video", "telegram_video") else "🎵"
            await self.edit_title(f"{icon} {song[1]}")

        Stats.tracks_played += 1
        Stats.requesters[song[4]] += 1
        Stats.history.appendleft(song[1])
        Stats.is_paused = False

        await self.send_playlist()
        log.info("Играет: %s, запросил %s", song[1], song[4])

    async def skip_current_playing(self):
        """Пропустить текущий трек и перейти к следующему."""
        if not playlist:
            await self.start_radio()
            return

        skipped = playlist.pop(0)
        log.info("Пропущен: %s", skipped[1])

        if skipped[3] in ("telegram", "telegram_video"):
            ext = "mp4" if skipped[3] == "telegram_video" else "m4a"
            tmp = f"downloads/{skipped[0]}.{ext}"
            try:
                if os.path.isfile(tmp):
                    os.remove(tmp)
            except Exception:
                pass

        if playlist:
            await self.play_song(playlist[0])
        else:
            await self.start_radio()

    # ── Баннер ─────────────────────────────────────────────────────────────────

    async def set_banner(self, url: str | None, pinned: bool | None = None):
        """
        Изменить баннер. pinned=True закрепляет его, так что он больше не
        будет уступать обложкам треков. pinned=False открепляет.
        pinned=None оставляет текущий режим закрепления как есть.
        Если сейчас что-то играет — применяем сразу.
        """
        Config.BANNER_URL = url
        if pinned is not None:
            Config.BANNER_PINNED = pinned
        if url is None:
            Config.BANNER_PINNED = False

        if playlist:
            await self.play_song(playlist[0])
        else:
            await self.start_radio()

    # ── Вспомогательные методы ────────────────────────────────────────────────

    async def _download_telegram(self, song: list, ext: str = "m4a") -> str | None:
        """Скачать медиафайл из Telegram и вернуть путь к нему."""
        try:
            os.makedirs("downloads", exist_ok=True)
            path = await bot.download_media(
                song[2],
                file_name=f"downloads/{song[0]}.{ext}",
            )
            return path
        except Exception as e:
            log.error("_download_telegram для '%s': %s", song[1], e)
            return None

    async def _skip_broken(self, song: list):
        """Удалить сломанный трек из очереди и продолжить."""
        log.warning("Пропускаем сломанный трек: %s", song[1])
        if playlist and playlist[0] is song:
            playlist.pop(0)
        if playlist:
            await self.play_song(playlist[0])
        else:
            await self.start_radio()

    async def _create_voice_chat(self):
        """Создать голосовой чат, если его нет."""
        try:
            peer = await USER.resolve_peer(CHAT_ID)
            await USER.invoke(
                CreateGroupCall(peer=peer, random_id=randint(10_000, 999_999_999))
            )
            await sleep(2)
            log.info("Голосовой чат создан")
        except Exception as e:
            log.error("Не удалось создать голосовой чат: %s", e)

    async def edit_title(self, title: str):
        """Изменить заголовок голосового чата."""
        if not EDIT_TITLE:
            return
        try:
            peer = await USER.resolve_peer(CHAT_ID)
            full = await USER.invoke(GetFullChannel(channel=peer))
            gc   = full.full_chat.call
            if gc:
                await USER.invoke(EditGroupCallTitle(
                    call=InputGroupCall(id=gc.id, access_hash=gc.access_hash),
                    title=title,
                ))
        except Exception as e:
            log.debug("edit_title: %s", e)

    async def get_admins(self, chat_id: int) -> list:
        """
        Вернуть список ID администраторов: статичные (.env AUTH_USERS) +
        динамические (добавленные через /admin) + реальные админы чата.
        Результат кэшируется — сбрасывается через add_admin/remove_admin.
        """
        if chat_id in ADMIN_LIST:
            return ADMIN_LIST[chat_id]

        admins = list(ADMINS) + list(Config.DYNAMIC_ADMINS)
        try:
            async for member in bot.get_chat_members(chat_id, filter="administrators"):
                if member.user and member.user.id not in admins:
                    admins.append(member.user.id)
        except Exception as e:
            log.warning("get_admins для %s: %s", chat_id, e)

        ADMIN_LIST[chat_id] = admins
        return admins

    async def add_admin(self, user_id: int) -> bool:
        """Добавить динамического админа. False, если он уже есть где-либо."""
        current = await self.get_admins(CHAT_ID)
        if user_id in current:
            return False
        Config.DYNAMIC_ADMINS.append(user_id)
        Config.save_dynamic_admins()
        ADMIN_LIST.clear()
        return True

    async def remove_admin(self, user_id: int) -> bool:
        """
        Удалить динамического админа. Можно удалить только тех, кто
        добавлен через панель — админов из .env или чата так не убрать,
        это осознанное ограничение.
        """
        if user_id not in Config.DYNAMIC_ADMINS:
            return False
        Config.DYNAMIC_ADMINS.remove(user_id)
        Config.save_dynamic_admins()
        ADMIN_LIST.clear()
        return True

    async def delete_after_delay(self, message):
        """Удалить сообщение бота через DELAY секунд."""
        if DELAY <= 0:
            return
        if getattr(message.chat, "type", "") in ("supergroup", "channel", "group"):
            await sleep(DELAY)
            try:
                await message.delete()
            except Exception:
                pass


# ─── Единственный экземпляр (все плагины импортируют этот объект) ─────────────
mp = MusicPlayer()


# ══════════════════════════════════════════════════════════════════════════════
#  Перезапуск бота — общая функция, чтобы её можно было вызвать и из
#  команды /restart (main.py), и из кнопки в панели (plugins/bot/panel.py)
#  без циклических импортов.
# ══════════════════════════════════════════════════════════════════════════════
def _restart_process():
    """Синхронная функция перезапуска, работает в отдельном потоке."""
    import sys
    from time import sleep as _time_sleep
    _time_sleep(2)
    os.system("git pull && pip install -r requirements.txt -q")
    os.execl(sys.executable, sys.executable, *sys.argv)


async def trigger_restart() -> bool:
    """
    Запустить перезапуск: обновить код с GitHub и перезапустить процесс
    (или перезапустить Heroku dyno, если бот там развёрнут).
    Возвращает True, если это Heroku-путь.
    """
    if Config.HEROKU_APP:
        Config.HEROKU_APP.restart()
        return True

    try:
        await call.leave_call(CHAT_ID)
    except Exception:
        pass

    from threading import Thread
    Thread(target=_restart_process, daemon=True).start()
    return False


# ══════════════════════════════════════════════════════════════════════════════
#  Динамический фильтр "только для администраторов"
#
#  filters.user([...]) в Pyrogram замораживает список в момент создания
#  фильтра. admin_filter вместо этого каждый раз заново спрашивает
#  mp.get_admins() — новый админ из панели сразу может пользоваться
#  командами, без перезапуска бота.
# ══════════════════════════════════════════════════════════════════════════════
async def _admin_check(_, __, update) -> bool:
    user = getattr(update, "from_user", None)
    if not user:
        return False
    admins = await mp.get_admins(CHAT_ID)
    return user.id in admins

admin_filter = filters.create(_admin_check)


# ══════════════════════════════════════════════════════════════════════════════
#  Обработчики событий PyTgCalls
# ══════════════════════════════════════════════════════════════════════════════

@call.on_update()
async def _on_call_update(_, update: Update):
    """Обработчик всех событий голосового чата."""

    if isinstance(update, StreamEnded):
        if update.chat_id != CHAT_ID:
            return
        if update.stream_type != StreamEnded.Type.AUDIO:
            return

        log.info("Поток завершился в чате %s", update.chat_id)

        if playlist:
            await mp.skip_current_playing()
        else:
            await sleep(1)
            await mp.start_radio()

    elif isinstance(update, ChatUpdate):
        if update.chat_id != CHAT_ID:
            return

        kicked_statuses = {
            ChatUpdate.Status.KICKED,
            ChatUpdate.Status.LEFT_GROUP,
            ChatUpdate.Status.CLOSED_VOICE_CHAT,
        }

        if update.status in kicked_statuses:
            log.warning("Статус чата изменился: %s, очищаем очередь", update.status)
            playlist.clear()
