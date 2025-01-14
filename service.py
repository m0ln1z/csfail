import asyncio
import logging
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from aiogram import Bot, Dispatcher, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токен бота и ID чата
botToken = "7381459756:AAFcqXCJtFjx-PJpDSVL4Wcs3543nltkzG8"
chatId = "-4751196447"

# Инициализация бота с увеличенным тайм-аутом и диспетчера
bot = Bot(token=botToken, session=AiohttpSession(timeout=120))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# URL и класс для парсинга
url = "https://5cs.fail/en/wheel"
className = "rounds-stats__color rounds-stats__color_20x"

# История спинов
spinHistory = []

# Функция для получения значения спина
def fetchSpinValue():
    chromeOptions = Options()
    chromeOptions.add_argument("--headless")
    chromeOptions.add_argument("--disable-gpu")
    chromeOptions.add_argument("--no-sandbox")
    chromeOptions.add_argument("--disable-dev-shm-usage")
    chromeOptions.add_argument("--disable-blink-features=AutomationControlled")
    chromeOptions.add_experimental_option("excludeSwitches", ["enable-automation"])
    chromeOptions.add_experimental_option("useAutomationExtension", False)
    chromeOptions.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
    )

    retries = 3
    for attempt in range(retries):
        try:
            driver = webdriver.Chrome(options=chromeOptions)
            driver.get(url)
            logging.info("Ожидание загрузки страницы...")

            element = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, f".{className}"))
            )

            logging.info("Элемент найден: %s", element.get_attribute("outerHTML"))
            spinValue = element.text.strip()

            try:
                return int(spinValue)
            except ValueError:
                logging.error("Неверное значение: %s. Не число.", spinValue)
                return None
        except Exception as e:
            logging.error("Ошибка: %s. Попытка %d/%d", e, attempt + 1, retries)
            if attempt < retries - 1:
                time.sleep(5)
        finally:
            if 'driver' in locals():
                driver.quit()

    return None

# Счетчик количества повторений одного значения spinValue
unchangedSpinValueCount = 0
unchangedSpinValueThreshold = 80
lastSentSpinValue = None
lastNotifiedSpinValue = None

# Асинхронная функция для проверки условий и отправки уведомлений
async def checkConditionsAndNotify():
    global spinHistory, lastSentSpinValue, lastNotifiedSpinValue, unchangedSpinValueCount

    spinValue = fetchSpinValue()
    if spinValue is None:
        return

    spinHistory.append(spinValue)
    if len(spinHistory) > 100:
        spinHistory.pop(0)

    logging.info(f"Обновление истории спинов: {spinHistory[-10:]}")

    if spinValue >= (lastSentSpinValue if lastSentSpinValue is not None else float('-inf')) or \
       (lastSentSpinValue is not None and lastSentSpinValue > spinHistory[-2] if len(spinHistory) > 1 else False):
        unchangedSpinValueCount += 1
        logging.info(
            f"Значение {spinValue} больше или равно предыдущему ({lastSentSpinValue}) "
            f"или последнее отправленное значение увеличилось. "
            f"Счётчик: {unchangedSpinValueCount}/{unchangedSpinValueThreshold}"
        )

        if unchangedSpinValueCount >= unchangedSpinValueThreshold:
            alertMessage = f"Значение {spinValue} повторяется или увеличивается уже {unchangedSpinValueThreshold} раз подряд!"
            await sendNotification(alertMessage)
            logging.info(f"Уведомление о повторении отправлено: {alertMessage}")
            unchangedSpinValueCount = 0
        return
    else:
        unchangedSpinValueCount = 0

    if spinValue != lastNotifiedSpinValue:
        message = f"{spinValue} золотых за последние 100 спинов"
        await sendNotification(message)
        lastNotifiedSpinValue = spinValue
        logging.info(f"Уведомление отправлено: {message}")

    lastSentSpinValue = spinValue

# Асинхронная функция для отправки уведомлений в Telegram
async def sendNotification(message):
    retries = 3
    for _ in range(retries):
        try:
            await bot.send_message(chatId, message)
            logging.info(f"Сообщение отправлено: {message}")
            break
        except Exception as e:
            logging.error(f"Ошибка отправки сообщения: {e}. Попытка повторить...")
            await asyncio.sleep(5)

# Основной цикл программы
async def main():
    asyncio.create_task(checkConditionsAndNotifyLoop())
    await dp.start_polling(bot)

# Циклическая проверка условий
async def checkConditionsAndNotifyLoop():
    while True:
        try:
            await checkConditionsAndNotify()
        except Exception as e:
            logging.error(f"Ошибка в цикле: {e}")
        await asyncio.sleep(26)

# Запуск программы
if __name__ == "__main__":
    import sys
    if sys.version_info >= (3, 8):
        asyncio.run(main())
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
