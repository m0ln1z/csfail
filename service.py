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

# Настроим логирование
logging.basicConfig(level=logging.INFO)

# Токен бота и ID чата
botToken = "7381459756:AAFcqXCJtFjx-PJpDSVL4Wcs3543nltkzG8"
chatId = "-4751196447"

# Инициализация бота с увеличенным тайм-аутом и диспетчера
bot = Bot(
    token=botToken,
    session=AiohttpSession(timeout=60)  # Тайм-аут для клиента Telegram
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# URL и класс для парсинга
url = "https://5cs.fail/en/wheel"
className = "rounds-stats__color rounds-stats__color_20x"

# История спинов
spinHistory = []

# Функция для получения значения спина с повторными попытками
def fetchSpinValue():
    chromeOptions = Options()
    chromeOptions.add_argument("--headless")
    chromeOptions.add_argument("--disable-gpu")
    chromeOptions.add_argument("--no-sandbox")
    chromeOptions.add_argument("--disable-dev-shm-usage")
    chromeOptions.add_argument("--disable-blink-features=AutomationControlled")
    chromeOptions.add_experimental_option("excludeSwitches", ["enable-automation"])
    chromeOptions.add_experimental_option("useAutomationExtension", False)

    # Минимизация загрузки ресурсов
    prefs = {"profile.managed_default_content_settings.images": 2}
    chromeOptions.add_experimental_option("prefs", prefs)

    # Минимизация размера окна
    chromeOptions.add_argument("window-size=800x600")

    chromeOptions.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
    )

    retries = 3
    driver = None
    for attempt in range(retries):
        try:
            if driver is None:
                driver = webdriver.Chrome(options=chromeOptions)
                driver.set_page_load_timeout(30)  # Время ожидания на загрузку страницы
                driver.get(url)
                logging.info("Ожидание загрузки страницы...")

            # Ожидаем только появления необходимого элемента
            element = WebDriverWait(driver, 30).until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".rounds-stats__color.rounds-stats__color_20x")))

            spinValue = element.text.strip()
            return int(spinValue) if spinValue.isdigit() else None

        except Exception as e:
            logging.error(f"Ошибка в Selenium: {e}. Попытка {attempt + 1}/{retries}")
            time.sleep(5)
            if driver:
                logging.info("Перезагружаем страницу...")
                driver.refresh()
                time.sleep(10)  # Увеличенный тайм-аут между перезагрузками

        finally:
            if driver:
                driver.quit()
            gc.collect()  # Очистка памяти после завершения работы с браузером

    return None

# Счетчик количества повторений одного значения spinValue
unchangedSpinValueCount = 0  
unchangedSpinValueThreshold = 43
lastSentSpinValue = None  
lastNotifiedSpinValue = None  

async def checkConditionsAndNotify():
    global spinHistory, lastSentSpinValue, lastNotifiedSpinValue, unchangedSpinValueCount

    spinValue = fetchSpinValue()
    if spinValue is None:
        return

    # Обновление истории спинов (хранится только 100 последних значений)
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
            alertMessage = f"Значение {spinValue} повторяется или увеличивается уже 85 раз подряд!"
            await sendNotification(alertMessage)
            logging.info(f"Уведомление о повторении отправлено: {alertMessage}")
            unchangedSpinValueCount = 0  
    else:
        unchangedSpinValueCount = 0

    # Логика для отправки текущего значения
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
        await asyncio.sleep(30)  # Увеличено время ожидания для снижения нагрузки

# Запуск программы
if __name__ == "__main__":
    import sys
    if sys.version_info >= (3, 8):
        asyncio.run(main()) 
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
