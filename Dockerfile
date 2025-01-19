# Используем минимальный базовый образ Python
FROM python:3.10-slim

# Отключаем буферизацию Python, чтобы логи сразу шли в stdout
ENV PYTHONUNBUFFERED=1

# Устанавливаем системные зависимости и необходимые инструменты
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        chromium \
        libnss3 \
        libgconf-2-4 \
        libasound2 \
        libappindicator3-1 \
        fonts-liberation \
        x11-utils \
        xauth \
        wget \
        unzip \
        curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта в контейнер
COPY . /app

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r requirements.txt

# Определяем версии Chromium и ChromeDriver динамически
RUN CHROME_VERSION=$(chromium --version | grep -oP '\d+\.\d+\.\d+\.\d+') && \
    CHROME_MAJOR=$(echo $CHROME_VERSION | cut -d. -f1) && \
    CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_MAJOR}") && \
    wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    rm /tmp/chromedriver.zip && \
    chmod +x /usr/local/bin/chromedriver && \
    apt-get remove -y unzip wget curl && \
    apt-get autoremove -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Указываем команду запуска — просто Python-скрипт
CMD ["python", "service.py"]