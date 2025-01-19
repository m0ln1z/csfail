# Используем официальный базовый образ Python
FROM python:3.10-slim

# Отключаем буферизацию Python, чтобы логи сразу шли в stdout
ENV PYTHONUNBUFFERED=1

# Устанавливаем необходимые системные зависимости и инструменты
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        curl \
        gnupg \
        ca-certificates \
        fonts-liberation \
        libnss3 \
        libgconf-2-4 \
        libasound2 \
        libappindicator3-1 \
        xdg-utils \
        && rm -rf /var/lib/apt/lists/*

# Добавляем ключ и репозиторий Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] https://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта в контейнер
COPY . /app

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r requirements.txt

# Удалите жестко закодированные переменные окружения из Dockerfile
# Вместо этого используйте их при запуске контейнера

# Запускаем приложение
CMD ["python", "service.py"]