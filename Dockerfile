# Используем официальный Python 3.11 образ
FROM python:3.11-slim

# Обновляем репозитории перед установкой
RUN apt-get update --fix-missing

# Устанавливаем необходимые системные зависимости для Selenium/Chrome
RUN apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    curl \
    unzip \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxi6 \
    libxtst6 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgdk-pixbuf2.0-0 \
    libpango-1.0-0 \
    libgdk-x11-2.0-0 \
    libgbm-dev \
    libasound2 \
    libappindicator3-1 \
    libdbus-1-3 \
    libnspr4 \
    libxss1 \
    fonts-liberation \
    libappindicator1 \
    libxtst6 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Google Chrome (или Chromium)
RUN wget -q -O - https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb > google-chrome.deb && \
    dpkg -i google-chrome.deb; \
    apt-get install -f -y && \
    rm google-chrome.deb

# Устанавливаем Python-зависимости
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальные файлы приложения в контейнер
COPY . /app/

# Устанавливаем переменные окружения для Chrome
ENV CHROME_BIN=/usr/bin/google-chrome
ENV DISPLAY=:99

# Настроим "headless" режим для Chrome
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libxss1 \
    libappindicator3-1 \
    libgdk-pixbuf2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Запускаем скрипт
CMD ["python", "your_script_name.py"]
