import os
import json
import logging
import asyncio
import time
import gc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

# ---------------------
# Глобальные переменные
# ---------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_35x.log"),
        logging.StreamHandler()
    ]
)

botToken = os.getenv("BOT_TOKEN")
chatId = os.getenv("CHAT_ID")

bot = Bot(token=botToken, session=AiohttpSession(timeout=60))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

url = "https://5cs.fail/en/wheel"
className = "rounds-stats__color rounds-stats__color_35x"

unchangedSpinValueCount = 0
unchangedSpinValueThreshold = 85
lastSentSpinValue = None
lastNotifiedSpinValue = None
spinHistory = []

STATE_FILE = "state_35x.json"

# ----------------------
# Глобальный WebDriver
# ----------------------
driver = None  # Храним экземпляр Selenium (Chrome) здесь

# ----------------------------
# Функции сохранения/загрузки
# ----------------------------
def load_state():
    global unchangedSpinValueCount, lastSentSpinValue, lastNotifiedSpinValue, spinHistory

    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
            unchangedSpinValueCount = data.get("unchangedSpinValueCount", 0)
            lastSentSpinValue = data.get("lastSentSpinValue", None)
            lastNotifiedSpinValue = data.get("lastNotifiedSpinValue", None)
            spinHistory = data.get("spinHistory", [])
            logging.info("Загружено состояние из state_35x.json")
        except Exception as e:
            logging.error(f"Ошибка при загрузке state_35x.json: {e}")
    else:
        logging.info("Файл state_35x.json не найден. Используем значения по умолчанию.")

def save_state():
    data = {
        "unchangedSpinValueCount": unchangedSpinValueCount,
        "lastSentSpinValue": lastSentSpinValue,
        "lastNotifiedSpinValue": lastNotifiedSpinValue,
        "spinHistory": spinHistory,
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
        logging.info("Состояние сохранено в state_35x.json")
    except Exception as e:
        logging.error(f"Ошибка при сохранении state_35x.json: {e}")

# --------------------------------
# Функции управления WebDriver
# --------------------------------
def create_driver():
    chromeOptions = Options()
    chromeOptions.add_argument("--headless")
    chromeOptions.add_argument("--disable-gpu")
    chromeOptions.add_argument("--no-sandbox")
    chromeOptions.add_argument("--disable-dev-shm-usage")
    chromeOptions.add_argument("--disable-blink-features=AutomationControlled")
    chromeOptions.add_experimental_option("excludeSwitches", ["enable-automation"])
    chromeOptions.add_experimental_option("useAutomationExtension", False)

    # Отключаем картинки
    prefs = {"profile.managed_default_content_settings.images": 2}
    chromeOptions.add_experimental_option("prefs", prefs)
    chromeOptions.add_argument("window-size=800x600")

    try:
        service = Service(ChromeDriverManager().install())
        driver_instance = webdriver.Chrome(service=service, options=chromeOptions)
        logging.info("ChromeDriver успешно запущен")
        driver_instance.set_page_load_timeout(30)
        return driver_instance
    except Exception as e:
        logging.error(f"Не удалось запустить ChromeDriver: {e}")
        raise

def get_driver():
    global driver
    if driver is None:
        logging.info("Создаём новый экземпляр ChromeDriver...")
        driver = create_driver()
    return driver

def close_driver():
    global driver
    if driver:
        logging.info("Закрываем WebDriver...")
        try:
            driver.quit()
            logging.info("WebDriver закрыт успешно.")
        except Exception as e:
            logging.error(f"Ошибка при закрытии WebDriver: {e}")
        driver = None
        gc.collect()

# ------------------------
# Сама логика с Selenium
# ------------------------
def fetchSpinValues(retries=3, delay=5):
    d = get_driver()
    for attempt in range(1, retries + 1):
        try:
            d.get(url)
            logging.info(f"Страница загружена (попытка {attempt})")

            wait = WebDriverWait(d, 30)
            main_element = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, className)
            ))
            main_value_text = main_element.text.strip()
            spinValue = int(main_value_text) if main_value_text.isdigit() else None
            return spinValue

        except Exception as e:
            logging.error(f"Ошибка в Selenium (попытка {attempt}): {e}")
            close_driver()
            time.sleep(delay)

    logging.error("Не удалось получить значение spinValue после всех попыток.")
    return None

# -------------------------------
# Проверка условий + Уведомления
# -------------------------------
async def checkConditionsAndNotify():
    global spinHistory, lastSentSpinValue, unchangedSpinValueCount

    spinValue = await asyncio.get_running_loop().run_in_executor(None, fetchSpinValues)
    if spinValue is None:
        return

    spinHistory.append(spinValue)
    if len(spinHistory) > 100:
        spinHistory.pop(0)

    if spinValue <= (lastSentSpinValue or float('-inf')):
        unchangedSpinValueCount += 1
        if unchangedSpinValueCount >= unchangedSpinValueThreshold:
            message = f"35x не выпадала {unchangedSpinValueThreshold} спинов подряд."
            await sendNotification(message)
            unchangedSpinValueCount = 0
    else:
        unchangedSpinValueCount = 0

    lastSentSpinValue = spinValue
    save_state()

async def sendNotification(message):
    retries = 3
    for attempt in range(1, retries + 1):
        try:
            await bot.send_message(chatId, message)
            logging.info(f"Сообщение отправлено: {message}")
            break
        except Exception as e:
            logging.error(f"Ошибка отправки сообщения (попытка {attempt}): {e}")
            await asyncio.sleep(5)

# --------------------
# Основной цикл
# --------------------
async def checkConditionsAndNotifyLoop():
    while True:
        try:
            await checkConditionsAndNotify()
        except Exception as e:
            logging.error(f"Ошибка в цикле: {e}")
            close_driver()
        await asyncio.sleep(26)

async def handle_start(message: types.Message):
    await message.answer("Бот 35x запущен и работает.")

def setup_handlers():
    @router.message(Command("start"))
    async def start_handler(message: types.Message):
        await handle_start(message)

async def main():
    load_state()
    setup_handlers()
    asyncio.create_task(checkConditionsAndNotifyLoop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Скрипт остановлен вручную.")
    except Exception as e:
        logging.error(f"Непредвиденная ошибка: {e}")