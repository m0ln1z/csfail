# Используем минимальный базовый образ Python
FROM python:3.10-slim

# Отключаем буферизацию Python, чтобы логи сразу шли в stdout
ENV PYTHONUNBUFFERED=1

# Устанавливаем системные зависимости (минимально необходимые для запуска headless Chrome)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        chromium \
        # Удаляем установку chromium-driver
        libnss3 \
        libgconf-2-4 \
        libasound2 \
        libappindicator3-1 \
        fonts-liberation \
        x11-utils \
        xauth && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Устанавливаем переменные для версий Chromium и ChromeDriver
ENV CHROME_VERSION=132.0.6834.83
ENV CHROMEDRIVER_VERSION=132.0.6834.83

# Загрузка и установка ChromeDriver
RUN wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip && \
    apt-get update && apt-get install -y unzip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    rm /tmp/chromedriver.zip && \
    chmod +x /usr/local/bin/chromedriver && \
    apt-get remove -y unzip && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта (включая service.py, requirements.txt и т.п.) в контейнер
COPY . /app

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r requirements.txt

# Указываем команду запуска — просто Python-скрипт
CMD ["python", "service.py"]