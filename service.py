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

from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

# ---------------------
# Глобальные переменные
# ---------------------
logging.basicConfig(level=logging.INFO)

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
unchangedSpinValueThreshold = 36
lastSentSpinValue = None
lastNotifiedSpinValue = None
valueBlueCount = 0
valueGreenCount = 0
valuePurpleCount = 0
lastBlueValue = None
lastGreenValue = None
lastPurpleValue = None
lastNotifiedBlueValue = None
lastNotifiedGreenValue = None
lastNotifiedPurpleValue = None
spinHistory = []

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
    global valueBlueCount, valueGreenCount, valuePurpleCount
    global lastBlueValue, lastGreenValue, lastPurpleValue
    global lastNotifiedBlueValue, lastNotifiedGreenValue, lastNotifiedPurpleValue

    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
            unchangedSpinValueCount = data.get("unchangedSpinValueCount", 0)
            lastSentSpinValue = data.get("lastSentSpinValue", None)
            lastNotifiedSpinValue = data.get("lastNotifiedSpinValue", None)
            spinHistory = data.get("spinHistory", [])
            valueBlueCount = data.get("valueBlueCount", 0)
            valueGreenCount = data.get("valueGreenCount", 0)
            valuePurpleCount = data.get("valuePurpleCount", 0)
            lastBlueValue = data.get("lastBlueValue", None)
            lastGreenValue = data.get("lastGreenValue", None)
            lastPurpleValue = data.get("lastPurpleValue", None)
            lastNotifiedBlueValue = data.get("lastNotifiedBlueValue", None)
            lastNotifiedGreenValue = data.get("lastNotifiedGreenValue", None)
            lastNotifiedPurpleValue = data.get("lastNotifiedPurpleValue", None)
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
        "valueBlueCount": valueBlueCount,
        "valueGreenCount": valueGreenCount,
        "valuePurpleCount": valuePurpleCount,
        "lastBlueValue": lastBlueValue,
        "lastGreenValue": lastGreenValue,
        "lastPurpleValue": lastPurpleValue,
        "lastNotifiedBlueValue": lastNotifiedBlueValue,
        "lastNotifiedGreenValue": lastNotifiedGreenValue,
        "lastNotifiedPurpleValue": lastNotifiedPurpleValue,
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

    driver_instance = webdriver.Chrome(options=chromeOptions)
    driver_instance.set_page_load_timeout(30)
    return driver_instance


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
    и получить значения spinValue для нескольких классов.
    Возвращает словарь с результатами. Если не удаётся — None.
    В случае получения нулевых значений, пытается перезапросить страницу.
    """
    d = get_driver()  # Получаем (или создаём) driver

    for attempt in range(1, retries + 1):
        try:
            # Загружаем страницу
            d.get(url)
            logging.info(f"Страница загружена, ищем элементы... (Попытка {attempt})")

            # Ждём элементы
            wait = WebDriverWait(d, 30)
            classes = [
                "rounds-stats__color rounds-stats__color_20x",
                "rounds-stats__color rounds-stats__color_2x",
                "rounds-stats__color rounds-stats__color_3x",
                "rounds-stats__color rounds-stats__color_5x",
            ]

            spin_values = {}
            for class_name in classes:
                try:
                    element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f".{class_name.replace(' ', '.')}")))
                    value = element.text.strip()
                    spin_values[class_name] = int(value) if value.isdigit() else None
                except Exception as e:
                    logging.warning(f"Не удалось найти элемент для {class_name}: {e}")
                    spin_values[class_name] = None

            # Проверяем, есть ли нулевые значения
            if all(v == 0 or v is None for v in spin_values.values()):
                logging.warning("Все полученные значения равны нулю или отсутствуют. Пытаемся перезапросить страницу.")
                raise ValueError("Получены некорректные нулевые значения.")
            
            # Если данные корректны, возвращаем их
            return spin_values

        except Exception as e:
            logging.error(f"Ошибка в Selenium при попытке {attempt}: {e}")
            if "DevToolsActivePort file doesn't exist" in str(e):
                logging.error("Критическая ошибка Chrome (DevToolsActivePort)! Падаем, чтобы перезапуститься...")
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
    global valueBlueCount, valueGreenCount, valuePurpleCount
    global lastBlueValue, lastGreenValue, lastPurpleValue
    global lastNotifiedBlueValue, lastNotifiedGreenValue, lastNotifiedPurpleValue

    # Получаем все значения спинов
    spin_values = fetchSpinValues()
    if spin_values is None:
        return  # Не удалось получить значения (не критическая ошибка), выходим

    # Обновление истории (хранится только 100 последних значений)
    spinValue = spin_values.get("rounds-stats__color rounds-stats__color_20x")
    if spinValue is not None:
        spinHistory.append(spinValue)
        if len(spinHistory) > 100:
            spinHistory.pop(0)
        logging.info(f"Обновление истории спинов: {spinHistory[-10:]}")

    # Обработка для каждого из новых элементов
    valueBlue = spin_values.get("rounds-stats__color rounds-stats__color_2x")
    valueGreen = spin_values.get("rounds-stats__color rounds-stats__color_3x")
    valuePurple = spin_values.get("rounds-stats__color rounds-stats__color_5x")
    logging.info(f"Получены новые значения: Blue={valueBlue}, Green={valueGreen}, Purple={valuePurple}")

    # Обновление счётчика для valueBlue
    if valueBlue is not None:
        if lastBlueValue is not None and valueBlue <= lastBlueValue:
            valueBlueCount += 1
            logging.info(f"Счётчик Blue увеличен до {valueBlueCount}")
        else:
            valueBlueCount = 0
            logging.info(f"Счётчик Blue сброшен")
        lastBlueValue = valueBlue

        if valueBlueCount >= 9 and valueBlue != lastNotifiedBlueValue:
            message = f"Синяя не выпадала 12 спинов подряд!"
            await sendNotification(message)
            lastNotifiedBlueValue = valueBlue
            logging.info(f"Уведомление отправлено: {message}")
            valueBlueCount = 0  # Сброс счетчика после уведомления

    # Обновление счётчика для valueGreen
    if valueGreen is not None:
        if lastGreenValue is not None and valueGreen <= lastGreenValue:
            valueGreenCount += 1
            logging.info(f"Счётчик Green увеличен до {valueGreenCount}")
        else:
            valueGreenCount = 0
            logging.info(f"Счётчик Green сброшен")
        lastGreenValue = valueGreen

        if valueGreenCount >= 6 and valueGreen != lastNotifiedGreenValue:
            message = f"Зелёная не выпадала 10 спинов подряд!"
            await sendNotification(message)
            lastNotifiedGreenValue = valueGreen
            logging.info(f"Уведомление отправлено: {message}")
            valueGreenCount = 0  # Сброс счетчика после уведомления

    # Обновление счётчика для valuePurple
    if valuePurple is not None:
        if lastPurpleValue is not None and valuePurple <= lastPurpleValue:
            valuePurpleCount += 1
            logging.info(f"Счётчик Purple увеличен до {valuePurpleCount}")
        else:
            valuePurpleCount = 0
            logging.info(f"Счётчик Purple сброшен")
        lastPurpleValue = valuePurple

        if valuePurpleCount >= 6 and valuePurple != lastNotifiedPurpleValue:
            message = f"Фиолетовая не выпадала 10 спинов подряд!"
            await sendNotification(message)
            lastNotifiedPurpleValue = valuePurple
            logging.info(f"Уведомление отправлено: {message}")
            valuePurpleCount = 0  # Сброс счетчика после уведомления

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
                    f"Последняя золотая (35х) была 85 спинов назад"
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
    Запускает бесконечный цикл, который раз в 60 секунд
    вызывает checkConditionsAndNotify().
    """
    while True:
        try:
            await checkConditionsAndNotify()
        except Exception as e:
            logging.error(f"Ошибка в цикле: {e}")
            close_driver()
        await asyncio.sleep(60)

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