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
unchangedSpinValueThreshold = 43
lastSentSpinValue = None
lastNotifiedSpinValue = None
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
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
            unchangedSpinValueCount = data.get("unchangedSpinValueCount", 0)
            lastSentSpinValue = data.get("lastSentSpinValue", None)
            lastNotifiedSpinValue = data.get("lastNotifiedSpinValue", None)
            spinHistory = data.get("spinHistory", [])
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
def fetchSpinValue():
    """
    Использует глобальный driver, чтобы открыть страницу
    и получить spinValue. Если не удаётся, возвращает None.
    При критической ошибке DevToolsActivePort - "роняем" скрипт.
    """
    d = get_driver()  # Получаем (или создаём) driver

    try:
        # Загружаем страницу
        d.get(url)
        logging.info("Страница загружена, ищем элемент...")

        # Ждём элемент
        element = WebDriverWait(d, 30).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".rounds-stats__color.rounds-stats__color_20x")
            )
        )

        spinValue = element.text.strip()
        return int(spinValue) if spinValue.isdigit() else None

    except Exception as e:
        error_text = str(e)
        logging.error(f"Ошибка в Selenium: {error_text}")

        # Если это именно DevToolsActivePort file doesn't exist
        if "DevToolsActivePort file doesn't exist" in error_text:
            logging.error("Критическая ошибка Chrome (DevToolsActivePort)! "
                          "Падаем, чтобы перезапуститься...")
            close_driver()
            # Поднимаем исключение, чтобы script упал и перезапустился в __main__
            raise RuntimeError("Critical Selenium error (DevToolsActivePort)") from e

        # Иначе - просто закрываем driver и возвращаем None
        close_driver()
        return None


# -------------------------------
# Проверка условий + Уведомления
# -------------------------------
async def checkConditionsAndNotify():
    global spinHistory, lastSentSpinValue, lastNotifiedSpinValue, unchangedSpinValueCount

    spinValue = fetchSpinValue()
    if spinValue is None:
        return  # Не удалось получить значение (не критическая ошибка), выходим

    # Обновление истории (хранится только 100 последних значений)
    spinHistory.append(spinValue)
    if len(spinHistory) > 100:
        spinHistory.pop(0)

    logging.info(f"Обновление истории спинов: {spinHistory[-10:]}")

    # -----------------------------------------------------------------
    # Логика счётчика (пример исходной):
    # Если текущее значение не меньше предыдущего -> увеличиваем счётчик
    # Иначе сбрасываем в 0
    # -----------------------------------------------------------------
    if (
        spinValue <= (lastSentSpinValue if lastSentSpinValue is not None else float('-inf'))
        or (lastSentSpinValue is not None
            and len(spinHistory) > 1
            and lastSentSpinValue > spinHistory[-2])
    ):
        unchangedSpinValueCount += 1
        logging.info(
            f"Значение {spinValue} >= предыдущего ({lastSentSpinValue}); "
            f"Счётчик: {unchangedSpinValueCount}/{unchangedSpinValueThreshold}"
        )

        if unchangedSpinValueCount >= unchangedSpinValueThreshold:
            alertMessage = (
                f"Значение {spinValue} повторяется или увеличивается уже 85 раз подряд!"
            )
            await sendNotification(alertMessage)
            logging.info(f"Уведомление о повторении отправлено: {alertMessage}")
            unchangedSpinValueCount = 0
    else:
        unchangedSpinValueCount = 0

    # Уведомление о текущем значении
    if spinValue != lastNotifiedSpinValue:
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
    for attempt in range(retries):
        try:
            await bot.send_message(chatId, message)
            logging.info(f"Сообщение отправлено: {message}")
            break
        except Exception as e:
            logging.error(f"Ошибка отправки сообщения: {e}. Повтор через 5 секунд...")
            await asyncio.sleep(5)


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


async def main():
    """
    Стартует бота (aiogram) и фоновую задачу checkConditionsAndNotifyLoop().
    """
    # При каждом запуске скрипта (после краша) - загружаем состояние:
    load_state()

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
            time.sleep(10)