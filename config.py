"""
╔══════════════════════════════════════════════════════════╗
║           RadioPlayerV3 — Конфигурация                  ║
║   Все настройки берутся из переменных окружения         ║
║   (.env файл локально, или Config Vars на Heroku)       ║
╚══════════════════════════════════════════════════════════╝
"""
import json
import os
from dotenv import load_dotenv

# Загружаем .env файл, если запускаем локально
load_dotenv()


class Config:

    # ══════════════════════════════════════════════════════════════
    # ОБЯЗАТЕЛЬНЫЕ — без них бот не запустится
    # ══════════════════════════════════════════════════════════════

    # Получить на https://my.telegram.org → "API development tools"
    API_ID   = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")

    # Токен бота — создать через @BotFather → /newbot
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")

    # Строка сессии юзербота — получить запустив: python3 gen_session.py
    # Юзербот нужен потому, что обычные боты не умеют входить в голосовые чаты
    SESSION = os.getenv("SESSION_STRING", "")

    # ID чата/канала, где будет играть музыка
    # Для групп/каналов — отрицательное число, например: -1001234567890
    # Узнать ID можно пересланным постом через @username_to_id_bot
    CHAT_ID = int(os.getenv("CHAT_ID", 0))

    # ══════════════════════════════════════════════════════════════
    # НЕОБЯЗАТЕЛЬНЫЕ — разумные значения по умолчанию
    # ══════════════════════════════════════════════════════════════

    # Название радиостанции — используется в приветствиях, /help, панели
    RADIO_NAME = os.getenv("RADIO_NAME", "Радио Лида")

    # Контакт поддержки, показывается обычным пользователям в /start
    SUPPORT_CONTACT = os.getenv("SUPPORT_CONTACT", "@Yakton_support")

    # Дополнительные администраторы бота (через пробел, ID или @username)
    # Пример: AUTH_USERS="123456789 987654321 @myusername"
    # (Администраторы чата добавляются автоматически)
    ADMINS: list = [
        int(a) if a.lstrip("-").isdigit() else a
        for a in os.getenv("AUTH_USERS", "").split()
        if a
    ]

    # Ссылка на радиопоток (по умолчанию — индийское радио Mirchi для теста)
    # Поменяй на свою: например http://icecast.example.com:8000/stream.mp3
    STREAM_URL = os.getenv("STREAM_URL", "http://peridot.streamguys.com:7150/Mirchi")

    # ID группы/канала для логов (статус бота, текущий трек и т.д.)
    # Оставь пустым, если логи не нужны
    LOG_GROUP = int(os.getenv("LOG_GROUP") or 0) or None

    # Если True — /play и /song доступны ТОЛЬКО администраторам
    # Если False — любой участник чата может добавить трек
    # По умолчанию True — бот задуман как закрытая панель управления,
    # а не паблик-сервис (см. NON_ADMIN_TEXT в plugins/bot/start.py)
    ADMIN_ONLY = os.getenv("ADMIN_ONLY", "True").lower() == "true"

    # Ответ на личные сообщения от незнакомцев (None = не отвечать)
    REPLY_MESSAGE = os.getenv("REPLY_MESSAGE") or None

    # Через сколько секунд удалять служебные сообщения бота (0 = не удалять)
    DELAY = int(os.getenv("DELAY") or 10)

    # Если True — заголовок голосового чата меняется на название трека
    EDIT_TITLE = os.getenv("EDIT_TITLE", "True").lower() != "false"

    # Заголовок голосового чата во время работы радио
    RADIO_TITLE = os.getenv("RADIO_TITLE", "📻 РАДИО ЛИДА | ПРЯМОЙ ЭФИР") or None

    # Максимальная длина трека в МИНУТАХ для команды /play
    # Треки длиннее этого лимита будут отклонены
    DURATION_LIMIT = int(os.getenv("MAXIMUM_DURATION") or 15)

    # Картинка-баннер, которая показывается как "видео" во время звука
    # (например: логотип радио, обложка). Можно оставить пустым —
    # тогда играет чистый звук без картинки. Меняется на лету: /banner
    BANNER_URL = os.getenv("BANNER_URL") or None

    # Если True — баннер не заменяется обложками треков (YouTube и т.д.),
    # висит одним и тем же, пока не выключишь. Переключается: /banner pin
    BANNER_PINNED = os.getenv("BANNER_PINNED", "False").lower() == "true"

    # ══════════════════════════════════════════════════════════════
    # HEROKU — нужно только при деплое на Heroku
    # ══════════════════════════════════════════════════════════════

    HEROKU_API_KEY  = os.getenv("HEROKU_API_KEY")   # Account → API Key
    HEROKU_APP_NAME = os.getenv("HEROKU_APP_NAME")   # Имя твоего Heroku-приложения
    HEROKU_APP      = None                            # Заполняется ниже

    # ══════════════════════════════════════════════════════════════
    # ДИНАМИЧЕСКИЕ АДМИНЫ — добавляются/удаляются через /admin панель,
    # хранятся в admins.json и переживают перезапуск бота.
    # Это ОТДЕЛЬНЫЙ список от ADMINS (тот берётся из .env и его можно
    # поменять только вручную) — так проще понимать, кого можно
    # снять кнопкой в панели, а кого нет.
    # ══════════════════════════════════════════════════════════════

    ADMINS_FILE = "admins.json"
    DYNAMIC_ADMINS: list = []

    @classmethod
    def load_dynamic_admins(cls):
        if os.path.isfile(cls.ADMINS_FILE):
            try:
                with open(cls.ADMINS_FILE, "r", encoding="utf-8") as f:
                    cls.DYNAMIC_ADMINS = json.load(f)
            except Exception as e:
                print(f"[admins.json] ⚠️ Не удалось прочитать: {e}")
                cls.DYNAMIC_ADMINS = []

    @classmethod
    def save_dynamic_admins(cls):
        try:
            with open(cls.ADMINS_FILE, "w", encoding="utf-8") as f:
                json.dump(cls.DYNAMIC_ADMINS, f)
        except Exception as e:
            print(f"[admins.json] ⚠️ Не удалось сохранить: {e}")

    # ══════════════════════════════════════════════════════════════
    # РАБОЧЕЕ СОСТОЯНИЕ — меняется в процессе работы бота
    # ══════════════════════════════════════════════════════════════

    msg:      dict = {}   # Ссылки на служебные сообщения (для редактирования/удаления)
    playlist: list = []   # Очередь треков — список списков [id, title, src, type, by]


Config.load_dynamic_admins()

# ─── Подключение к Heroku (только если оба ключа заданы) ─────────────────────
if Config.HEROKU_API_KEY and Config.HEROKU_APP_NAME:
    try:
        import heroku3
        Config.HEROKU_APP = heroku3.from_key(Config.HEROKU_API_KEY).apps()[Config.HEROKU_APP_NAME]
        print("[Heroku] ✅ Подключение успешно")
    except Exception as _err:
        print(f"[Heroku] ⚠️  Не удалось подключиться: {_err}")
