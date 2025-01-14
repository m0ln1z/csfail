# Используем минимальный базовый образ Python
FROM python:3.10-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    libnss3 \
    libgconf-2-4 \
    libasound2 \
    libappindicator3-1 \
    fonts-liberation \
    x11-utils \
    xvfb \
    xauth && \  # Устанавливаем xauth
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY . /app

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p /dev/shm && chmod 1777 /dev/shm

# Указываем переменные окружения для Selenium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_DRIVER=/usr/bin/chromedriver

# Команда запуска с использованием xvfb-run для эмуляции виртуального экрана
CMD ["xvfb-run", "--auto-servernum", "--server-args='-screen 0 1280x1024x24'", "python", "service.py"]
