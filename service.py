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
from webdriver_manager.chrome import ChromeDriverManager  # Добавлено

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
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

botToken = "7381459756:AAFcqXCJtFjx-PJpDSVL4Wcs3543nltkzG8"
chatId = "-4751196447"


bot = Bot(token=botToken, session=AiohttpSession(timeout=60))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

url = "https://5cs.fail/en/wheel"
className = "rounds-stats__color rounds-stats__color_20x"

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
missing2xThreshold = 12
missing3xThreshold = 10
missing4xThreshold = 10

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
    """
    Читаем состояние из state.json, если он существует.
    """
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

            # Загрузка новых счетчиков
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
    """
    Сохраняем текущее состояние в state.json.
    """
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
    """
    Создаёт новый экземпляр ChromeDriver с нужными опциями и возвращает его.
    """
    chromeOptions = Options()
    chromeOptions.add_argument("--headless")
    chromeOptions.add_argument("--disable-gpu")
    chromeOptions.add_argument("--no-sandbox")
    chromeOptions.add_argument("--disable-dev-shm-usage")
    chromeOptions.add_argument("--disable-blink-features=AutomationControlled")
    chromeOptions.add_experimental_option("excludeSwitches", ["enable-automation"])
    chromeOptions.add_experimental_option("useAutomationExtension", False)

    # Отключаем картинки (для экономии ресурсов)
    prefs = {"profile.managed_default_content_settings.images": 2}
    chromeOptions.add_experimental_option("prefs", prefs)

    chromeOptions.add_argument("window-size=800x600")
    chromeOptions.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
    )

    try:
        # Используем webdriver-manager для автоматической установки ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver_instance = webdriver.Chrome(service=service, options=chromeOptions)
        logging.info("ChromeDriver успешно запущен")
        driver_instance.set_page_load_timeout(30)
        return driver_instance
    except Exception as e:
        logging.error(f"Не удалось запустить ChromeDriver: {e}")
        raise

def get_driver():
    """
    Возвращает актуальный WebDriver. Если он ещё не создан
    или упал в предыдущем цикле — пересоздаём.
    """
    global driver
    if driver is None:
        logging.info("Создаём новый экземпляр ChromeDriver...")
        driver = create_driver()
    return driver

def close_driver():
    """
    Закрывает WebDriver и освобождает память.
    """
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
    """
    Использует глобальный driver, чтобы открыть страницу
    и получить значения spinValue для основного класса и классов 2x, 3x, 4x внутри <div data-swiper-slide-index="0">.
    Возвращает словарь с результатами. Если не удаётся — None.
    В случае получения нулевых значений, пытается перезапросить страницу.
    """
    d = get_driver()  # Получаем (или создаём) driver

    for attempt in range(1, retries + 1):
        try:
            # Загружаем страницу
            d.get(url)
            logging.info(f"Страница загружена, ищем элементы... (Попытка {attempt})")

            # Ждём основной элемент для 20x
            wait = WebDriverWait(d, 30)
            main_element = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, '.rounds-stats__color.rounds-stats__color_20x')
            ))
            main_value_text = main_element.text.strip()
            spin_values = {}
            spin_values['20x'] = int(main_value_text) if main_value_text.isdigit() else None
            logging.info(f"Основное значение 20x найдено: {spin_values['20x']}")

            # Проверяем, является ли значение 20x нулевым или отсутствующим
            if spin_values['20x'] is None:
                logging.warning("Основное значение 20x отсутствует. Пытаемся перезапросить страницу.")
                raise ValueError("Получено некорректное значение 20x.")

            # Теперь ищем родительский div с data-swiper-slide-index="0"
            parent_div = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'div[data-swiper-slide-index="0"]')
            ))
            logging.info("Родительский div с data-swiper-slide-index='0' найден.")

            # Ищем элементы для 2x, 3x, 4x внутри parent_div
            # Предполагается, что элементы имеют классы 'game_2x', 'game_3x', 'game_4x'
            # Замените селекторы ниже на реальные классы, если они отличаются

            game_presence = {
                '2x': False,
                '3x': False,
                '4x': False,
            }

            # Ищем все элементы <a> с классом, содержащим 'game_'
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

            # Объединяем результаты
            spin_values.update(game_presence)

            return spin_values

        except Exception as e:
            logging.error(f"Ошибка в Selenium при попытке {attempt}: {e}")
            if "DevToolsActivePort file doesn't exist" in str(e):
                logging.error("Критическая ошибка Chrome (DevToolsActivePort)! Перезапускаем WebDriver...")
                close_driver()
                raise RuntimeError("Critical Selenium error (DevToolsActivePort)") from e
            else:
                logging.info(f"Попытка {attempt} не удалась. Ждём {delay} секунд перед следующей попыткой...")
                close_driver()
                time.sleep(delay)

    logging.error("Не удалось получить корректные значения spinValue после всех попыток.")
    return None

# -------------------------------
# Проверка условий + Уведомления
# -------------------------------
async def checkConditionsAndNotify():
    global spinHistory, lastSentSpinValue, lastNotifiedSpinValue, unchangedSpinValueCount
    global missing2xCount, missing3xCount, missing4xCount
    global lastNotified2x, lastNotified3x, lastNotified4x

    # Получаем все значения спинов и наличие классов 2x, 3x, 4x
    spin_values = fetchSpinValues()
    if spin_values is None:
        return  # Не удалось получить значения (не критическая ошибка), выходим

    # Обновление истории (хранится только 100 последних значений)
    spinValue = spin_values.get("20x")  # Исправлено на '20x'
    if spinValue is not None:
        spinHistory.append(spinValue)
        if len(spinHistory) > 100:
            spinHistory.pop(0)
        logging.info(f"Обновление истории спинов: {spinHistory[-10:]}")

    # Обработка для основного значения (20x)
    if spinValue is not None:
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
                alertMessage = (
                    f"Последняя золотая (35х) была {unchangedSpinValueThreshold} спинов назад"
                )
                await sendNotification(alertMessage)
                logging.info(f"Уведомление о повторении отправлено: {alertMessage}")
                unchangedSpinValueCount = 0
        else:
            unchangedSpinValueCount = 0

        if spinValue <= 2 and spinValue != lastNotifiedSpinValue:
            message = f"{spinValue} золотых за последние 100 спинов"
            await sendNotification(message)
            lastNotifiedSpinValue = spinValue
            logging.info(f"Уведомление отправлено: {message}")

        # Обновляем "последнее отправленное" значение
        lastSentSpinValue = spinValue

    # Обработка для 2x, 3x, 4x
    # Проверяем наличие классов
    is_2x_present = spin_values.get('2x', False)
    is_3x_present = spin_values.get('3x', False)
    is_4x_present = spin_values.get('4x', False)

    logging.info(f"Наличие 2x: {is_2x_present}, 3x: {is_3x_present}, 4x: {is_4x_present}")

    # Обновление счётчика для 2x
    if is_2x_present:
        if missing2xCount != 0:
            logging.info("Счётчик 2x сброшен, так как 2x присутствует")
        missing2xCount = 0
        lastNotified2x = None
    else:
        missing2xCount += 1
        logging.info(f"Счётчик 2x увеличен до {missing2xCount}")
        if missing2xCount >= missing2xThreshold and missing2xCount != lastNotified2x:
            message = "2x не выпадала 12 спинов подряд!"
            await sendNotification(message)
            lastNotified2x = missing2xCount
            logging.info(f"Уведомление отправлено: {message}")
            missing2xCount = 0  # Сброс счетчика после уведомления

    # Обновление счётчика для 3x
    if is_3x_present:
        if missing3xCount != 0:
            logging.info("Счётчик 3x сброшен, так как 3x присутствует")
        missing3xCount = 0
        lastNotified3x = None
    else:
        missing3xCount += 1
        logging.info(f"Счётчик 3x увеличен до {missing3xCount}")
        if missing3xCount >= missing3xThreshold and missing3xCount != lastNotified3x:
            message = "3x не выпадала 10 спинов подряд!"
            await sendNotification(message)
            lastNotified3x = missing3xCount
            logging.info(f"Уведомление отправлено: {message}")
            missing3xCount = 0  # Сброс счетчика после уведомления

    # Обновление счётчика для 4x
    if is_4x_present:
        if missing4xCount != 0:
            logging.info("Счётчик 4x сброшен, так как 4x присутствует")
        missing4xCount = 0
        lastNotified4x = None
    else:
        missing4xCount += 1
        logging.info(f"Счётчик 4x увеличен до {missing4xCount}")
        if missing4xCount >= missing4xThreshold and missing4xCount != lastNotified4x:
            message = "4x не выпадала 10 спинов подряд!"
            await sendNotification(message)
            lastNotified4x = missing4xCount
            logging.info(f"Уведомление отправлено: {message}")
            missing4xCount = 0  # Сброс счетчика после уведомления

    # Сохраняем состояние после каждого успешного обновления
    save_state()

async def sendNotification(message):
    """
    Асинхронно отправляет сообщение в Telegram.
    """
    retries = 3
    for attempt in range(1, retries + 1):
        try:
            await bot.send_message(chatId, message)
            logging.info(f"Сообщение отправлено: {message}")
            break
        except Exception as e:
            logging.error(f"Ошибка отправки сообщения: {e}. Повтор через 5 секунд... (Попытка {attempt})")
            if attempt < retries:
                await asyncio.sleep(5)
            else:
                logging.error("Не удалось отправить сообщение после всех попыток.")

# --------------------
# Основной цикл
# --------------------
async def checkConditionsAndNotifyLoop():
    """
    Запускает бесконечный цикл, который раз в 26 секунд
    вызывает checkConditionsAndNotify().
    """
    while True:
        try:
            await checkConditionsAndNotify()
        except Exception as e:
            logging.error(f"Ошибка в цикле: {e}")
            close_driver()
        await asyncio.sleep(26)  # Изменено с 60 на 26 секунд

async def handle_start(message: types.Message):
    """
    Обработчик команды /start для бота.
    """
    await message.answer("Бот запущен и работает.")

def setup_handlers():
    """
    Настраивает обработчики для aiogram.
    """
    @router.message(Command("start"))
    async def start_handler(message: types.Message):
        await handle_start(message)

async def main():
    """
    Стартует бота (aiogram) и фоновую задачу checkConditionsAndNotifyLoop().
    """
    # При каждом запуске скрипта (после краша) - загружаем состояние:
    load_state()

    # Настраиваем обработчики
    setup_handlers()

    # Стартуем фоновую задачу проверки
    asyncio.create_task(checkConditionsAndNotifyLoop())

    # Запускаем aiogram-поллинг
    await dp.start_polling(bot)

if __name__ == "__main__":
    import sys

    # Цикл перезапуска (если упадёт вообще весь скрипт)
    while True:
        try:
            if sys.version_info >= (3, 8):
                asyncio.run(main())
            else:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(main())
        except Exception as e:
            logging.error(f"Скрипт упал с ошибкой: {e}. Перезапускаем через 10 секунд.")
            close_driver()
            time.sleep(10)
