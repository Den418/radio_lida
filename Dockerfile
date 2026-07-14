# RadioPlayerV3 — Dockerfile
#
# Нужен только если разворачиваешь бота через Docker (Heroku Container
# Registry, Railway, Render, свой VPS и т.п.) И по каким-то причинам
# не подходит static-ffmpeg из requirements.txt (например, сервер режет
# исходящие соединения к GitHub). В остальных случаях этот файл не нужен —
# ffmpeg и ffprobe сами подтянутся при первом запуске.
#
# Сборка:   docker build -t radio-lida .
# Запуск:   docker run --env-file .env radio-lida

FROM python:3.11-slim

# ffmpeg даёт нам сразу и ffmpeg, и ffprobe — обе команды из одного пакета
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "main.py"]
