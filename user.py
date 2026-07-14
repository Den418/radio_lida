"""
Юзербот (userbot) — обычный аккаунт Telegram, управляемый программно.

Зачем нужен?
  Telegram не даёт обычным ботам входить в голосовые чаты.
  Именно юзербот будет сидеть в голосовом чате и воспроизводить аудио.
  Твой бот (@BotFather) будет принимать команды, а юзербот — их выполнять.

Строку сессии (SESSION_STRING) получаешь через:
  python3 gen_session.py
"""
from pyrogram import Client
from config import Config

USER = Client(
    "RadioPlayerUser",        # Имя файла сессии — создастся RadioPlayerUser.session
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    session_string=Config.SESSION,   # Строка сессии вместо интерактивного логина
)
