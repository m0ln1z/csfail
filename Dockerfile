# Используем базовый образ Python
FROM python:3.10-slim

# Устанавливаем необходимые системные пакеты
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    xvfb \
    libxi6 \
    libgconf-2-4 \
    libnss3 \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    xdg-utils \
    chromium \
    chromium-driver && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY . /app

# Устанавливаем зависимости проекта
RUN pip install --no-cache-dir -r requirements.txt

# Открываем порт для приложения (опционально, если требуется)
EXPOSE 8000

# Команда для запуска приложения
CMD ["python", "service.py"]
