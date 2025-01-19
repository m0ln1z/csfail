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
        logging.FileHandler("bot_234x.log"),
        logging.StreamHandler()
    ]
)

botToken = os.getenv("BOT_TOKEN_234X")
chatId = os.getenv("CHAT_ID_234X")

bot = Bot(token=botToken, session=AiohttpSession(timeout=60))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

url = "https://5cs.fail/en/wheel"

missing2xCount = 0
missing3xCount = 0
missing4xCount = 0

# Пороги для уведомлений
missing2xThreshold = 11
missing3xThreshold = 9
missing4xThreshold = 9

# Последние уведомленные значения
lastNotified2x = None
lastNotified3x = None
lastNotified4x = None

STATE_FILE = "state_234x.json"

# ----------------------
# Глобальный WebDriver
# ----------------------
driver = None  # Храним экземпляр Selenium (Chrome) здесь

# ----------------------------
# Функции сохранения/загрузки
# ----------------------------
def load_state():
    global missing2xCount, missing3xCount, missing4xCount
    global lastNotified2x, lastNotified3x, lastNotified4x

    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
            missing2xCount = data.get("missing2xCount", 0)
            missing3xCount = data.get("missing3xCount", 0)
            missing4xCount = data.get("missing4xCount", 0)

            lastNotified2x = data.get("lastNotified2x", None)
            lastNotified3x = data.get("lastNotified3x", None)
            lastNotified4x = data.get("lastNotified4x", None)

            logging.info("Загружено состояние из state_234x.json")
        except Exception as e:
            logging.error(f"Ошибка при загрузке state_234x.json: {e}")
    else:
        logging.info("Файл state_234x.json не найден. Используем значения по умолчанию.")

def save_state():
    data = {
        "missing2xCount": missing2xCount,
        "missing3xCount": missing3xCount,
        "missing4xCount": missing4xCount,
        "lastNotified2x": lastNotified2x,
        "lastNotified3x": lastNotified3x,
        "lastNotified4x": lastNotified4x,
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
        logging.info("Состояние сохранено в state_234x.json")
    except Exception as e:
        logging.error(f"Ошибка при сохранении state_234x.json: {e}")

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
            parent_div = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'div[data-swiper-slide-index="0"]')
            ))

            game_presence = {'2x': False, '3x': False, '4x': False}

            game_elements = parent_div.find_elements(By.CSS_SELECTOR, "a.game[class*='game_']")
            for elem in game_elements:
                class_attr = elem.get_attribute("class")
                if "game_2x" in class_attr:
                    game_presence['2x'] = True
                elif "game_3x" in class_attr:
                    game_presence['3x'] = True
                elif "game_4x" in class_attr:
                    game_presence['4x'] = True

            logging.info(f"Наличие классов 2x, 3x, 4x: {game_presence}")
            return game_presence

        except Exception as e:
            logging.error(f"Ошибка в Selenium (попытка {attempt}): {e}")
            close_driver()
            time.sleep(delay)

    logging.error("Не удалось получить значения после всех попыток.")
    return None

# -------------------------------
# Проверка условий + Уведомления
# -------------------------------
async def checkConditionsAndNotify():
    global missing2xCount, missing3xCount, missing4xCount
    global lastNotified2x, lastNotified3x, lastNotified4x

    spin_presence = await asyncio.get_running_loop().run_in_executor(None, fetchSpinValues)
    if spin_presence is None:
        return

    is_2x_present = spin_presence.get('2x', False)
    is_3x_present = spin_presence.get('3x', False)
    is_4x_present = spin_presence.get('4x', False)

    if not is_2x_present:
        missing2xCount += 1
        if missing2xCount >= missing2xThreshold and missing2xCount != lastNotified2x:
            await sendNotification("2x не выпадала 12 спинов подряд!")
            lastNotified2x = missing2xCount
    else:
        missing2xCount = 0

    if not is_3x_present:
        missing3xCount += 1
        if missing3xCount >= missing3xThreshold and missing3xCount != lastNotified3x:
            await sendNotification("3x не выпадала 10 спинов подряд!")
            lastNotified3x = missing3xCount
    else:
        missing3xCount = 0

    if not is_4x_present:
        missing4xCount += 1
        if missing4xCount >= missing4xThreshold and missing4xCount != lastNotified4x:
            await sendNotification("4x не выпадала 10 спинов подряд!")
            lastNotified4x = missing4xCount
    else:
        missing4xCount = 0

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
    await message.answer("Бот 2x, 3x, 4x запущен и работает.")

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