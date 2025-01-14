# Используем минимальный базовый образ Python
FROM python:3.10-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    libnss3 \
    libgconf-2-4 \
    fonts-liberation && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY . /app

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r requirements.txt

# Указываем переменные окружения для Selenium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_DRIVER=/usr/bin/chromedriver

# Команда запуска
CMD ["python", "service.py"]
