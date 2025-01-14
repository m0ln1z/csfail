import asyncio
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from aiogram import Bot, Dispatcher, types, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

# Токен бота и ID чата
botToken = "7381459756:AAFcqXCJtFjx-PJpDSVL4Wcs3543nltkzG8"
chatId = "-4751196447"

# Инициализация бота с увеличенным тайм-аутом и диспетчера
bot = Bot(
    token=botToken,
    session=AiohttpSession(timeout=120)  # Тайм-аут для клиента Telegram
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
    chromeOptions.add_argument("--headless")  # Для работы в фоновом режиме
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
            print("Ожидание загрузки страницы...")

            # Ожидание появления элемента
            element = WebDriverWait(driver, 60).until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".rounds-stats__color.rounds-stats__color_20x")))

            print("Элемент найден:", element.get_attribute("outerHTML"))
            spinValue = element.text.strip()

            try:
                return int(spinValue)
            except ValueError:
                print(f"Неверное значение: {spinValue}. Не число.")
                return None
        except Exception as e:
            print(f"Ошибка: {e}. Попытка {attempt + 1}/{retries}")
            if attempt < retries - 1:
                time.sleep(5)
        finally:
            if 'driver' in locals():
                driver.quit()

    return None



# Счетчик количества повторений одного значения spinValue
unchangedSpinValueCount = 0  # Счётчик повторений значения
unchangedSpinValueThreshold = 80  # Порог, после которого отправляется сообщение
lastSentSpinValue = None  # Последнее отправленное значение
lastNotifiedSpinValue = None  # Последнее значение, для которого было отправлено уведомление


# Асинхронная функция для проверки условий и отправки уведомлений
async def checkConditionsAndNotify():
    """Функция проверки условий и отправки уведомлений."""
    global spinHistory, lastSentSpinValue, lastNotifiedSpinValue, unchangedSpinValueCount

    # Получение последнего значения спина
    spinValue = fetchSpinValue()
    if spinValue is None:
        return

    # Обновление истории спинов (хранится только 100 последних значений)
    spinHistory.append(spinValue)
    if len(spinHistory) > 100:
        spinHistory.pop(0)

    # Отладочная информация
    print(f"Обновление истории спинов: {spinHistory[-10:]}")

    # Проверяем, совпадает ли новое значение с последним отправленным
    if spinValue == lastSentSpinValue:
        unchangedSpinValueCount += 1
        print(f"Значение {spinValue} повторяется. Счётчик: {unchangedSpinValueCount}/{unchangedSpinValueThreshold}")
        
        # Если значение не меняется 80 раз, отправляем сообщение о повторении
        if unchangedSpinValueCount >= unchangedSpinValueThreshold:
            alertMessage = f"Значение {spinValue} не меняется уже {unchangedSpinValueThreshold} раз!"
            await sendNotification(alertMessage)
            print(f"Уведомление о повторении отправлено: {alertMessage}")
            unchangedSpinValueCount = 0  # Сбрасываем счётчик
        return
    else:
        # Если значение изменилось, сбрасываем счётчик
        unchangedSpinValueCount = 0

    # Проверяем, отправлялось ли уведомление с текущим значением
    if spinValue != lastNotifiedSpinValue:
        # Формируем сообщение о значении спина
        message = f"{spinValue} золотых за последние 100 спинов"
        await sendNotification(message)
        lastNotifiedSpinValue = spinValue  # Обновляем последнее уведомленное значение
        print(f"Уведомление отправлено: {message}")

    # Обновляем последнее отправленное значение
    lastSentSpinValue = spinValue


# Асинхронная функция для отправки уведомлений в Telegram
async def sendNotification(message):
    """Функция для отправки уведомлений в Telegram."""
    retries = 3
    for _ in range(retries):
        try:
            await bot.send_message(chatId, message)
            print(f"Сообщение отправлено: {message}")
            break
        except Exception as e:
            print(f"Ошибка отправки сообщения: {e}. Попытка повторить...")
            await asyncio.sleep(5)

# Основной цикл программы
async def main():
    """Основной цикл программы."""
    asyncio.create_task(checkConditionsAndNotifyLoop())  # Запускаем фоновую задачу
    await dp.start_polling(bot)  # Стартуем бота

# Циклическая проверка условий
async def checkConditionsAndNotifyLoop():
    """Циклическая проверка условий."""
    while True:
        try:
            await checkConditionsAndNotify()
        except Exception as e:
            print(f"Ошибка в цикле: {e}")
        await asyncio.sleep(26)  # Проверка раз в 26 секунд

# Запуск программы
if __name__ == "__main__":
    import sys
    if sys.version_info >= (3, 8):
        asyncio.run(main())  # Для Python 3.8+
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())  # Для более старых версий Python
