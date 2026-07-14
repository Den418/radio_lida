"""
╔══════════════════════════════════════════════════════════╗
║         Генератор строки сессии юзербота                ║
║                                                          ║
║  Запусти: python3 gen_session.py                        ║
║  Скопируй SESSION_STRING и вставь в .env или Heroku     ║
╚══════════════════════════════════════════════════════════╝

⚠️  ВАЖНО:
  • Запускай ОДИН РАЗ на своём компьютере
  • Никогда не давай строку сессии посторонним — это полный доступ к аккаунту
  • Используй отдельный аккаунт (не основной) для юзербота
"""
import asyncio
from pyrogram import Client
from dotenv import load_dotenv
import os

load_dotenv()


async def generate():
    print("=" * 55)
    print("  Генератор сессии для RadioPlayerV3")
    print("=" * 55)
    print()
    print("Этот скрипт создаёт строку сессии (SESSION_STRING)")
    print("для юзербота, который будет входить в голосовые чаты.")
    print()

    # Берём API_ID и API_HASH из .env или вводим вручную
    api_id = os.getenv("API_ID") or input("Введи API_ID (с https://my.telegram.org): ").strip()
    api_hash = os.getenv("API_HASH") or input("Введи API_HASH: ").strip()

    print()
    print("Сейчас откроется авторизация в Telegram.")
    print("Введи номер телефона (с кодом страны, например +79001234567),")
    print("затем код подтверждения из Telegram.")
    print()

    async with Client(
        "gen_session_temp",
        api_id=int(api_id),
        api_hash=api_hash,
    ) as app:
        session_string = await app.export_session_string()

    # Удаляем временный файл сессии
    if os.path.isfile("gen_session_temp.session"):
        os.remove("gen_session_temp.session")

    print()
    print("=" * 55)
    print("✅ СТРОКА СЕССИИ СГЕНЕРИРОВАНА!")
    print("=" * 55)
    print()
    print("Скопируй всё между линиями ↓↓↓")
    print("-" * 55)
    print(session_string)
    print("-" * 55)
    print()
    print("Куда вставить SESSION_STRING:")
    print("  • Локально: добавь строку в .env файл")
    print("  • Heroku: Settings → Config Vars → SESSION_STRING")
    print()


if __name__ == "__main__":
    asyncio.run(generate())
