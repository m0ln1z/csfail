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

# Обработчик приветствия
@router.message(lambda message: message.text.lower() == "привет")
async def hello(message: types.Message):
    """Обработчик, который отвечает на сообщение 'Привет'."""
    print(f"Полученное сообщение: {message.text}")
    await message.answer("Привет! Чем могу помочь?")

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

lastSentSpinValue = None

# Асинхронная функция для проверки условий и отправки уведомлений
async def checkConditionsAndNotify():
    """Функция проверки условий и отправки уведомлений."""
    global spinHistory, lastSentSpinValue

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

    # Если новое значение спина совпадает с последним отправленным, ничего не делаем
    if spinValue == lastSentSpinValue:
        print(f"Значение золотой {spinValue} не изменено. Пропускаем уведомление.")
        return

    # Формируем сообщение в зависимости от значения спина
    message = f"{spinValue} золотых за последние 100 спинов"
    
    # Отправляем уведомление и обновляем последнее отправленное значение
    await sendNotification(message)
    lastSentSpinValue = spinValue
    print(f"Уведомление отправлено: {message}")

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
        await asyncio.sleep(60)  # Проверка раз в минуту

# Запуск программы
if __name__ == "__main__":
    import sys
    if sys.version_info >= (3, 8):
        asyncio.run(main())  # Для Python 3.8+
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())  # Для более старых версий Python
