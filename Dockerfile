# Используем официальный образ Python (3.11) в режиме "slim" (Debian/Ubuntu)
FROM python:3.11-slim

# Устанавливаем необходимые системные зависимости для Pyppeteer/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    gconf-service \
    libasound2 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgcc1 \
    libgconf-2-4 \
    libgdk-pixbuf2.0-0 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    ca-certificates \
    fonts-liberation \
    libappindicator1 \
    libnss3 \
    lsb-release \
    wget \
    xdg-utils \
    git \
    curl \
    # Дополнительные пакеты, которые часто требуются
    libgbm-dev \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем переменные окружения для pyppeteer
ENV PYPPETEER_HOME=/pyppeteer
ENV PYPPETEER_LAUNCH_OPTS='{"args":["--no-sandbox","--disable-setuid-sandbox"]}'

# Создаём директорию под код
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt /app/requirements.txt

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальные файлы проекта в контейнер
COPY . /app

# Запускаем основной скрипт при старте контейнера
CMD ["python", "service.py"]