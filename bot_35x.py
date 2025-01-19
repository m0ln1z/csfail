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

botToken = os.getenv("BOT_TOKEN_35X")
chatId = os.getenv("CHAT_ID_35X")

bot = Bot(token=botToken, session=AiohttpSession(timeout=60))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

url = "https://5cs.fail/en/wheel"
className = "rounds-stats__color rounds-stats__color_35x"  # Изменено на 35x

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
    """
    Читаем состояние из state_35x.json, если он существует.
    """
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
    """
    Сохраняем текущее состояние в state_35x.json.
    """
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
    и получить значения spinValue для 35x внутри <div data-swiper-slide-index="0">.
    Возвращает словарь с результатами. Если не удаётся — None.
    В случае получения нулевых значений, пытается перезапросить страницу.
    """
    d = get_driver()  # Получаем (или создаём) driver

    for attempt in range(1, retries + 1):
        try:
            # Загружаем страницу
            d.get(url)
            logging.info(f"Страница загружена, ищем элементы... (Попытка {attempt})")

            # Ждём основной элемент для 35x
            wait = WebDriverWait(d, 30)
            main_element = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, '.rounds-stats__color.rounds-stats__color_35x')
            ))
            main_value_text = main_element.text.strip()
            spin_values = {}
            spin_values['35x'] = int(main_value_text) if main_value_text.isdigit() else None
            logging.info(f"Основное значение 35x найдено: {spin_values['35x']}")

            # Проверяем, является ли значение 35x нулевым или отсутствующим
            if spin_values['35x'] is None:
                logging.warning("Основное значение 35x отсутствует. Пытаемся перезапросить страницу.")
                raise ValueError("Получено некорректное значение 35x.")

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

    loop = asyncio.get_running_loop()
    spin_values = await loop.run_in_executor(None, fetchSpinValues)
    if spin_values is None:
        return  # Не удалось получить значения (не критическая ошибка), выходим

    # Обновление истории (хранится только 100 последних значений)
    spinValue = spin_values.get("35x")
    if spinValue is not None:
        spinHistory.append(spinValue)
        if len(spinHistory) > 100:
            spinHistory.pop(0)
        logging.info(f"Обновление истории спинов: {spinHistory[-10:]}")

    # Обработка для основного значения (35x)
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
    await message.answer("Бот 35x запущен и работает.")

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
    try:
        # При каждом запуске скрипта (после краша) - загружаем состояние:
        load_state()

        # Настраиваем обработчики
        setup_handlers()

        # Стартуем фоновую задачу проверки
        asyncio.create_task(checkConditionsAndNotifyLoop())

        # Запускаем aiogram-поллинг
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Скрипт упал с ошибкой: {e}. Перезапускаем через 10 секунд.")
        close_driver()
        await asyncio.sleep(10)
        await main()

if __name__ == "__main__":
    import sys

    # Запуск основного асинхронного цикла
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Скрипт остановлен вручную.")
    except Exception as e:
        logging.error(f"Непредвиденная ошибка: {e}")