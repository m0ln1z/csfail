import os
import json
import logging
import asyncio
import time
import gc
import sys  # <-- добавили sys
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

# --------------------
# Глобальные настройки
# --------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()]
)

botToken_35x = os.getenv("BOT_TOKEN")
chatId_35x = os.getenv("CHAT_ID")

botToken_other = os.getenv("BOT_TOKEN_234X")
chatId_other = os.getenv("CHAT_ID_234X")

bot_35x = Bot(token=botToken_35x, session=AiohttpSession(timeout=60))
bot_other = Bot(token=botToken_other, session=AiohttpSession(timeout=60))

storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

url = "https://6cs.fail/en/wheel"

unchangedSpinValueCount = 0
unchangedSpinValueThreshold = 85
lastSentSpinValue = None
lastNotifiedSpinValue = None
spinHistory = []

# Новые счетчики для отслеживания отсутствия 2x, 3x, 4x
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

STATE_FILE = "state.json"

# ----------------------
# Глобальный WebDriver
# ----------------------
driver = None  # Храним экземпляр Selenium (Chrome) здесь

# ----------------------------
# Функции сохранения/загрузки
# ----------------------------
def load_state():
    global unchangedSpinValueCount, lastSentSpinValue, lastNotifiedSpinValue, spinHistory
    global missing2xCount, missing3xCount, missing4xCount
    global lastNotified2x, lastNotified3x, lastNotified4x

    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
            unchangedSpinValueCount = data.get("unchangedSpinValueCount", 0)
            lastSentSpinValue = data.get("lastSentSpinValue", None)
            lastNotifiedSpinValue = data.get("lastNotifiedSpinValue", None)
            spinHistory = data.get("spinHistory", [])

            missing2xCount = data.get("missing2xCount", 0)
            missing3xCount = data.get("missing3xCount", 0)
            missing4xCount = data.get("missing4xCount", 0)

            lastNotified2x = data.get("lastNotified2x", None)
            lastNotified3x = data.get("lastNotified3x", None)
            lastNotified4x = data.get("lastNotified4x", None)

            logging.info("Загружено состояние из state.json")
        except Exception as e:
            logging.error(f"Ошибка при загрузке state.json: {e}")
    else:
        logging.info("Файл state.json не найден. Используем значения по умолчанию.")

def save_state():
    data = {
        "unchangedSpinValueCount": unchangedSpinValueCount,
        "lastSentSpinValue": lastSentSpinValue,
        "lastNotifiedSpinValue": lastNotifiedSpinValue,
        "spinHistory": spinHistory,
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
        logging.info("Состояние сохранено в state.json")
    except Exception as e:
        logging.error(f"Ошибка при сохранении state.json: {e}")

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
    chromeOptions.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
    )

    try:
        service = Service(ChromeDriverManager().install())
        driver_instance = webdriver.Chrome(service=service, options=chromeOptions)
        logging.info("ChromeDriver успешно запущен")
        driver_instance.set_page_load_timeout(25)
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

# -------------------------
# Единоразовая загрузка URL
# -------------------------
def load_page_once():
    d = get_driver()
    try:
        d.get(url)
        logging.info("Страница загружена один раз. Дальше не перезагружаем.")
        # Небольшая пауза, чтобы страница успела дорендерить динамические элементы
        time.sleep(3)
    except Exception as e:
        logging.error(f"Ошибка при загрузке страницы {url}: {e}")
        close_driver()
        raise

# ------------------------
# Чтение обновлённых данных
# ------------------------
def fetchSpinValues():
    """
    Читаем необходимые значения напрямую из уже загруженной страницы,
    не делаем повторных get/refresh. Предполагается, что страница
    динамически обновляет DOM.
    """
    d = get_driver()

    try:
        # При каждом вызове просто пытаемся прочитать текущие данные
        wait = WebDriverWait(d, 15)

        # Основное значение 20x
        main_element = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, ".rounds-stats__color.rounds-stats__color_20x")
        ))
        main_value_text = main_element.text.strip()
        spin_values = {}
        spin_values['20x'] = int(main_value_text) if main_value_text.isdigit() else None

        if spin_values['20x'] is None:
            logging.warning("Некорректное значение 20x (None).")

        # Ищем общий родитель с data-swiper-slide-index="0"
        parent_div = d.find_element(By.CSS_SELECTOR, 'div[data-swiper-slide-index="0"]')

        # Ищем элементы <a> с классом, содержащим 'game_2x', 'game_3x', 'game_4x'
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

        spin_values.update(game_presence)
        return spin_values

    except Exception as e:
        logging.error(f"Ошибка при чтении данных со страницы: {e}")
        # Закрываем браузер, чтобы при следующем цикле пересоздать
        close_driver()
        return None

# -------------------------------------
# Функции checkConditionsAndNotify
# -------------------------------------
async def checkConditionsAndNotify():
    global spinHistory, lastSentSpinValue, lastNotifiedSpinValue, unchangedSpinValueCount
    global missing2xCount, missing3xCount, missing4xCount
    global lastNotified2x, lastNotified3x, lastNotified4x

    loop = asyncio.get_running_loop()
    spin_values = await loop.run_in_executor(None, fetchSpinValues)
    if spin_values is None:
        return  # Не удалось получить значения, выходим

    spinValue = spin_values.get("20x")

    # Обновление истории
    if spinValue is not None:
        spinHistory.append(spinValue)
        if len(spinHistory) > 100:
            spinHistory.pop(0)

    # ------------------------------
    # Проверки и уведомления
    # ------------------------------
    if spinValue is not None:
        # Проверка отсутствия роста 20x
        if (
            spinValue <= (lastSentSpinValue if lastSentSpinValue is not None else float('-inf'))
            or (lastSentSpinValue is not None
                and len(spinHistory) > 1
                and lastSentSpinValue > spinHistory[-2])
        ):
            unchangedSpinValueCount += 1
            logging.info(
                f"Значение {spinValue} <= предыдущего ({lastSentSpinValue}); "
                f"Счётчик: {unchangedSpinValueCount}/{unchangedSpinValueThreshold}"
            )
            if unchangedSpinValueCount >= unchangedSpinValueThreshold:
                alertMessage = f"Последняя золотая (35х) была {unchangedSpinValueThreshold} спинов назад"
                await sendNotification(alertMessage, notification_type="35x")
                unchangedSpinValueCount = 0
        else:
            unchangedSpinValueCount = 0

        # Пример проверки на минимум 20x за последние 100 спинов
        if spinValue <= 2 and spinValue != lastNotifiedSpinValue:
            message = f"{spinValue} золотых за последние 100 спинов"
            await sendNotification(message, notification_type="35x")
            lastNotifiedSpinValue = spinValue

        lastSentSpinValue = spinValue

    # Проверка для 2x, 3x, 4x
    is_2x_present = spin_values.get('2x', False)
    is_3x_present = spin_values.get('3x', False)
    is_4x_present = spin_values.get('4x', False)

    if is_2x_present:
        missing2xCount = 0
        lastNotified2x = None
    else:
        missing2xCount += 1
        if missing2xCount >= missing2xThreshold and missing2xCount != lastNotified2x:
            message = "2x не выпадала 12 спинов подряд!"
            await sendNotification(message, notification_type="other")
            lastNotified2x = missing2xCount
            missing2xCount = 0

    if is_3x_present:
        missing3xCount = 0
        lastNotified3x = None
    else:
        missing3xCount += 1
        if missing3xCount >= missing3xThreshold and missing3xCount != lastNotified3x:
            message = "3x не выпадала 10 спинов подряд!"
            await sendNotification(message, notification_type="other")
            lastNotified3x = missing3xCount
            missing3xCount = 0

    if is_4x_present:
        missing4xCount = 0
        lastNotified4x = None
    else:
        missing4xCount += 1
        if missing4xCount >= missing4xThreshold and missing4xCount != lastNotified4x:
            message = "4x не выпадала 10 спинов подряд!"
            await sendNotification(message, notification_type="other")
            lastNotified4x = missing4xCount
            missing4xCount = 0

    save_state()

async def sendNotification(message, notification_type="other"):
    retries = 3
    for attempt in range(1, retries + 1):
        try:
            if notification_type == "35x":
                await bot_35x.send_message(chatId_35x, message)
                logging.info(f"Сообщение отправлено через бот для 35x: {message}")
            else:
                await bot_other.send_message(chatId_other, message)
                logging.info(f"Сообщение отправлено через бот для других: {message}")
            break
        except Exception as e:
            logging.error(
                f"Ошибка отправки сообщения через {notification_type} бот: {e}. "
                f"Повтор через 5 секунд... (Попытка {attempt})"
            )
            if attempt < retries:
                await asyncio.sleep(5)
            else:
                logging.error(f"Не удалось отправить сообщение после всех попыток.")

# --------------------
# Основной цикл
# --------------------
async def checkConditionsAndNotifyLoop():
    interval = 26  
    while True:
        loop_start_time = time.time()
        logging.info("Начало итерации цикла проверки условий.")
        try:
            await checkConditionsAndNotify()
        except Exception as e:
            logging.error(f"Ошибка в цикле: {e}")
            close_driver()
            # Критическая ошибка — завершаем скрипт, чтобы Docker перезапустил
            sys.exit(1)

        loop_end_time = time.time()
        elapsed_time = loop_end_time - loop_start_time
        logging.info(f"Итерация цикла завершена. Время выполнения: {elapsed_time:.2f} секунд.")
        sleep_duration = max(0, interval - elapsed_time)
        logging.info(f"Ожидание перед следующей итерацией: {sleep_duration:.2f} секунд.")
        await asyncio.sleep(sleep_duration)

async def handle_start(message: types.Message):
    await message.answer("Бот запущен и работает.")

def setup_handlers():
    @router.message(Command("start"))
    async def start_handler(message: types.Message):
        await handle_start(message)

async def main():
    try:
        load_state()
        setup_handlers()

        get_driver()
        load_page_once()

        asyncio.create_task(checkConditionsAndNotifyLoop())

        await dp.start_polling(bot_35x)
    except Exception as e:
        logging.error(f"Скрипт упал с ошибкой: {e}. Отключаемся, чтобы Docker перезапустил контейнер.")
        close_driver()
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Скрипт остановлен вручную.")
    except Exception as e:
        logging.error(f"Непредвиденная ошибка: {e}")
        close_driver()
        sys.exit(1)
