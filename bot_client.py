"""
Клиент бота (отдельный модуль).

Зачем вынесен в отдельный файл?
  В оригинале бот создавался в utils.py, а потом СНОВА в main.py —
  это два разных подключения к одному bot_token. Telegram такое не любит.

  Вынося бота сюда, мы решаем проблему: и utils.py, и main.py, и плагины
  импортируют ОДИН и тот же объект — нет дублирования.
"""
from pyrogram import Client
from config import Config

bot = Client(
    "RadioPlayerBot",                 # Имя файла сессии
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(root="plugins.bot"), # Pyrogram сам загрузит все файлы из plugins/bot/
)
