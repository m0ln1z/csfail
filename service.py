import os
import json
import logging
import asyncio
import time
import gc
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException

from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

# ---- Для цветных логов (ANSI) ----
RESET = "\033[0m"
RED   = "\033[31m"
GREEN = "\033[32m"
YELLOW= "\033[33m"
BLUE  = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"

# --------------------
# Глобальные настройки
# --------------------
logging.basicConfig(
    level=logging.DEBUG,  # Изменено с INFO на DEBUG
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

# Новые счётчики для 2x, 3x, 4x
missing2xCount = 0
missing3xCount = 0
missing4xCount = 0

missing2xThreshold = 11
missing3xThreshold = 9
missing4xThreshold = 9

lastNotified2x = None
lastNotified3x = None
lastNotified4x = None

STATE_FILE = "state.json"

# ----------------------
# Глобальный WebDriver
# ----------------------
driver = None  # Экземпляр Selenium (Chrome) здесь

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
        logging.info("Страница загружена. Дальше не перезагружаем, ждём динамических обновлений.")
        time.sleep(3)  # Небольшая пауза для первичной отрисовки
    except Exception as e:
        logging.error(f"Ошибка при загрузке страницы {url}: {e}")
        close_driver()
        raise

# ------------------------
# Чтение обновлённых данных
# ------------------------
def fetchSpinValues():
    """
    Читаем сразу 4 числовых значения по классам rounds-stats__color_2x, 3x, 5x, 20x
    + определяем флаги is_2x, is_3x, is_4x по старой логике из a.game.game_2x/... .
    """
    d = get_driver()
    data = {
        "val_2x": None,
        "val_3x": None,
        "val_5x": None,
        "val_20x": None,

        # Чтобы сохранить совместимость со старым кодом:
        "main_20x": None,

        # Флаги (как раньше)
        "2x": False,
        "3x": False,
        "4x": False
    }

    try:
        wait = WebDriverWait(d, 5)

        # --- Читаем 4 "крупных" числа (2x/3x/5x/20x) ---
        elem_2x = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".rounds-stats__color.rounds-stats__color_2x")
            )
        )
        data["val_2x"] = int(elem_2x.text.strip())

        elem_3x = d.find_element(By.CSS_SELECTOR, ".rounds-stats__color.rounds-stats__color_3x")
        data["val_3x"] = int(elem_3x.text.strip())

        elem_5x = d.find_element(By.CSS_SELECTOR, ".rounds-stats__color.rounds-stats__color_5x")
        data["val_5x"] = int(elem_5x.text.strip())

        elem_20x = d.find_element(By.CSS_SELECTOR, ".rounds-stats__color.rounds-stats__color_20x")
        val_20x = int(elem_20x.text.strip())

        data["val_20x"] = val_20x
        data["main_20x"] = val_20x  # сохраняем в старое поле

        # --- Как раньше: проверяем наличие game_2x, game_3x, game_4x ---
        parent_div = d.find_element(By.CSS_SELECTOR, 'div[data-swiper-slide-index="0"]')
        game_elements = parent_div.find_elements(By.CSS_SELECTOR, "a.game[class*='game_']")

        for elem in game_elements:
            class_attr = elem.get_attribute("class")
            if "game_2x" in class_attr:
                data["2x"] = True
            elif "game_3x" in class_attr:
                data["3x"] = True
            elif "game_4x" in class_attr:
                data["4x"] = True

        # Добавляем логирование считанных значений
        logging.debug(f"[DEBUG] Считанные значения: {data}")

    except Exception as e:
        logging.exception("Ошибка при чтении данных со страницы")
        close_driver()
        raise

    return data

# ------------------
# Логика уведомлений
# ------------------
async def checkConditionsAndNotify(spin_data):
    """
    Принимаем уже считанный spin_data, в котором:
      spin_data["main_20x"] -> int/None
      spin_data["2x"], spin_data["3x"], spin_data["4x"] -> bool

    Запускаем все проверки и отправляем уведомления при необходимости.
    """
    global spinHistory, lastSentSpinValue, lastNotifiedSpinValue, unchangedSpinValueCount
    global missing2xCount, missing3xCount, missing4xCount
    global lastNotified2x, lastNotified3x, lastNotified4x

    spinValue = spin_data["main_20x"]

    # Цвет для логов
    color_str = CYAN  # по умолчанию
    if spin_data["2x"]:
        color_str = GREEN
    elif spin_data["3x"]:
        color_str = YELLOW
    elif spin_data["4x"]:
        color_str = RED

    logging.info(f"{color_str}Прочитан новый спин! main_20x={spinValue}, "
                 f"2x={spin_data['2x']}, 3x={spin_data['3x']}, 4x={spin_data['4x']}{RESET}")

    # --- ЛОГИКА СЧЁТЧИКА (исправленная) ---
    if spinValue is not None:
        # Добавляем логирование типов и значений
        logging.debug(f"[DEBUG] spinValue type: {type(spinValue)}, value: {spinValue}")
        logging.debug(f"[DEBUG] lastSentSpinValue type: {type(lastSentSpinValue)}, value: {lastSentSpinValue}")

        if lastSentSpinValue is None:
            # Первая инициализация (например, при старте бота)
            unchangedSpinValueCount = 0
            logging.info("Первый спин, инициализируем lastSentSpinValue и обнуляем счётчик.")
        else:
            # Если текущее значение > предыдущего => сброс
            if spinValue > lastSentSpinValue:
                unchangedSpinValueCount = 0
                logging.info(
                    f"Значение 20x={spinValue} > предыдущего ({lastSentSpinValue}). "
                    "Счётчик остановок сброшен."
                )
            else:
                # Если меньше или равно => увеличиваем счётчик
                unchangedSpinValueCount += 1
                logging.info(
                    f"Значение 20x={spinValue} <= предыдущего ({lastSentSpinValue}). "
                    f"Счётчик остановок: {unchangedSpinValueCount}/{unchangedSpinValueThreshold}"
                )

                # Если счётчик достиг порога, отправляем уведомление
                if unchangedSpinValueCount >= unchangedSpinValueThreshold:
                    alertMessage = f"Последняя золотая (35x) была {unchangedSpinValueThreshold} спинов назад!"
                    await sendNotification(alertMessage, notification_type="35x")
                    unchangedSpinValueCount = 0

        # Обновляем lastSentSpinValue (в конце логики)
        lastSentSpinValue = spinValue
        logging.debug(f"[DEBUG] Обновлено lastSentSpinValue: {lastSentSpinValue}")
    else:
        # Если почему-то spinValue == None (ошибка парсинга?)
        # Можно также обнулить счётчик или сделать что-то ещё
        unchangedSpinValueCount = 0
        logging.info("spinValue == None. Счётчик остановок сброшен.")

    # Пример проверки «если spinValue <= 2» (осталось как в примере)
    if spinValue is not None and spinValue <= 2 and spinValue != lastNotifiedSpinValue:
        message = f"{spinValue} золотых за последние 100 спинов!"
        await sendNotification(message, notification_type="35x")
        lastNotifiedSpinValue = spinValue

    # --- Проверка для 2x, 3x, 4x ---
    is_2x_present = spin_data['2x']
    is_3x_present = spin_data['3x']
    is_4x_present = spin_data['4x']

    # 2x
    if is_2x_present:
        missing2xCount = 0
        lastNotified2x = None
    else:
        missing2xCount += 1
        if missing2xCount >= missing2xThreshold and missing2xCount != lastNotified2x:
            message = "2x не выпадала 12+ спинов подряд!"
            await sendNotification(message, notification_type="other")
            lastNotified2x = missing2xCount
            missing2xCount = 0

    # 3x
    if is_3x_present:
        missing3xCount = 0
        lastNotified3x = None
    else:
        missing3xCount += 1
        if missing3xCount >= missing3xThreshold and missing3xCount != lastNotified3x:
            message = "3x не выпадала 10+ спинов подряд!"
            await sendNotification(message, notification_type="other")
            lastNotified3x = missing3xCount
            missing3xCount = 0

    # 4x
    if is_4x_present:
        missing4xCount = 0
        lastNotified4x = None
    else:
        missing4xCount += 1
        if missing4xCount >= missing4xThreshold and missing4xCount != lastNotified4x:
            message = "4x не выпадала 10+ спинов подряд!"
            await sendNotification(message, notification_type="other")
            lastNotified4x = missing4xCount
            missing4xCount = 0

    # Сохраняем всё
    save_state()

async def sendNotification(message, notification_type="other"):
    """
    Уведомление в нужный бот (35x или other).
    """
    retries = 3
    for attempt in range(1, retries + 1):
        try:
            if notification_type == "35x":
                await bot_35x.send_message(chatId_35x, message)
                logging.info(f"{MAGENTA}Сообщение отправлено через бот для 35x: {message}{RESET}")
            else:
                await bot_other.send_message(chatId_other, message)
                logging.info(f"{MAGENTA}Сообщение отправлено через бот для других: {message}{RESET}")
            break
        except Exception as e:
            logging.error(
                f"Ошибка отправки сообщения через {notification_type} бот: {e}. "
                f"Повтор через 5 секунд... (Попытка {attempt})"
            )
            if attempt < retries:
                await asyncio.sleep(5)
            else:
                logging.error("Не удалось отправить сообщение после всех попыток.")

# -----------------------------------------------------
# Основная логика: ждём, когда на сайте поменяется спин
# -----------------------------------------------------
async def watchForNewSpinLoop():
    d = get_driver()

    try:
        # Считаем начальные данные
        last_spin_data = fetchSpinValues()
        if not last_spin_data:
            logging.error("Не удалось считать начальные данные со страницы.")
            raise SystemExit(1)
        
        logging.debug(f"[DEBUG] Начальные данные: {last_spin_data}")

        while True:
            try:
                current_spin_data = fetchSpinValues()
                logging.debug(f"[DEBUG] Текущие данные: {current_spin_data}")

                if current_spin_data != last_spin_data:
                    logging.info("Обнаружены изменения в данных спина.")
                    await checkConditionsAndNotify(current_spin_data)
                    last_spin_data = current_spin_data
                else:
                    logging.warning("Timeout: числа 2x/3x/5x/20x не изменились за время ожидания. Продолжаем ожидание...")

                await asyncio.sleep(15)  # Ждём 15 секунд перед следующей проверкой

            except Exception as e:
                logging.error(f"Ошибка в watchForNewSpinLoop: {e}")
                break

    except Exception as e:
        logging.error(f"Критическая ошибка в watchForNewSpinLoop: {e}")
        raise SystemExit(1)
    finally:
        close_driver()
        logging.info("WebDriver закрыт.")

# --------------------------
# Aiogram: /start и main
# --------------------------
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

        asyncio.create_task(watchForNewSpinLoop())

        # Запускаем поллинг бота 35x (как в вашем коде)
        await dp.start_polling(bot_35x)

    except Exception as e:
        logging.error(f"Скрипт упал с ошибкой: {e}. Выходим.")
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