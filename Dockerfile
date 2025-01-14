# Используем минимальный базовый образ Python
FROM python:3.10-slim

# Отключаем буферизацию Python, чтобы логи сразу шли в stdout
ENV PYTHONUNBUFFERED=1

# Устанавливаем системные зависимости (минимально необходимые для запуска headless Chrome)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        libnss3 \
        libgconf-2-4 \
        libasound2 \
        libappindicator3-1 \
        fonts-liberation \
        x11-utils \
        # Если нужен xvfb, оставляйте, но раз у вас headless:
        # xvfb \
        xauth && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта (включая service.py, requirements.txt и т.п.) в контейнер
COPY . /app

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r requirements.txt

# Команда запуска — просто Python-скрипт
CMD ["python", "service.py"]