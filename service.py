import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from aiogram import Bot, Dispatcher, types, Router
from aiogram.fsm.storage.memory import MemoryStorage

# Токен бота и ID чата
botToken = "7381459756:AAFcqXCJtFjx-PJpDSVL4Wcs3543nltkzG8"
chatId = "-4751196447"

# Инициализация бота и диспетчера
bot = Bot(token=botToken)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# URL и класс для парсинга
url = "https://5cs.fail/en/wheel"
className = "rounds-stats__color rounds-stats__color_20x"

# История спинов
spinHistory = []


@router.message(lambda message: message.text.lower() == "привет")
async def hello(message: types.Message):
    """Обработчик, который отвечает на сообщение 'Привет'."""
    print(f"Полученное сообщение: {message.text}")
    await message.answer("Привет! Чем могу помочь?")


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

    driver = webdriver.Chrome(options=chromeOptions)
    driver.get(url)

    try:
        print("Ожидание загрузки страницы...")

        # Ожидание появления элемента с увеличенным временем
        element = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".rounds-stats__color.rounds-stats__color_20x"))
        )
        
        # Если элемент найден, выводим его HTML для проверки
        print("Элемент найден:")
        print(element.get_attribute("outerHTML"))
        
        spinValue = element.text.strip()
        print(f"Забираем значение спина: {spinValue}")
        
        # Преобразуем в целое число, если удается
        try:
            return int(spinValue)
        except ValueError:
            print(f"Неверное значение спина: {spinValue}. Не могу преобразовать в тип integer.")
            return None

    except Exception as e:
        print(f"Ошибка получения данных со спинов: {e}")
        
        # Сохраняем HTML и скриншот для отладки
        with open("page_source.html", "w", encoding="utf-8") as file:
            file.write(driver.page_source)
        driver.save_screenshot("screenshot.png")
        print("HTML страницы и скриншот сохранены для анализа.")
        
        return None

    finally:
        driver.quit()


lastSentSpinValue = None  

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

    print(f"Обновление истории спинов: {spinHistory[-10:]}")  # Отладочная информация

    # Если новое значение спина совпадает с последним отправленным, ничего не делаем
    if spinValue == lastSentSpinValue:
        print(f"Значение золотой {spinValue} не изменено. Пропускаем уведомление.")
        return

    # Формируем сообщение в зависимости от значения спина
    if spinValue == 0:
        message = "0 золотых за последние 100 спинов"
    elif spinValue == 1:
        message = "1 золотая за последние 100 спинов"
    elif spinValue == 2:
        message = "2 золотые за последние 100 спинов"
    elif spinValue == 3:
        message = "3 золотые за последние 100 спинов"
    elif spinValue == 4:
        message = "4 золотых за последние 100 спинов"
    elif spinValue == 5:
        message = "5 золотых за последние 100 спинов"
    elif spinValue == 35:
        if 35 not in spinHistory[-100:]:
            message = "0 золотых за последние 100 спинов"
        else:
            # Логика для проверки последнего появления значения 35
            last35Index = len(spinHistory) - 1 - spinHistory[::-1].index(35)
            spinsSinceLast35 = len(spinHistory) - last35Index - 1
            if spinsSinceLast35 >= 85:
                message = f"С последней золотой 35х прошло {spinsSinceLast35} спинов"
            else:
                print(f"С момента последнего 35 прошло {spinsSinceLast35} спинов. Уведомление не отправлено.")
                return  
    else:
        print(f"Неизвестное значение: {spinValue}. Пропуск.")
        return

    # Отправляем уведомление и обновляем последнее отправленное значение
    await sendNotification(message)
    lastSentSpinValue = spinValue
    print(f"Уведомление отправлено: {message}")


async def sendNotification(message):
    """Функция для отправки уведомлений в Telegram."""
    for _ in range(3):  # Отправляем сообщение 3 раза
        await bot.send_message(chatId, message)
        await asyncio.sleep(5) # Delay для отправки 3 сообщений

async def main():
    """Основной цикл программы."""
    # Запускаем проверку условий в фоне
    asyncio.create_task(checkConditionsAndNotifyLoop())
    # Стартуем бота
    await dp.start_polling(bot)


async def checkConditionsAndNotifyLoop():
    """Циклическая проверка условий."""
    while True:
        await checkConditionsAndNotify()
        await asyncio.sleep(60)  # Проверяем раз в минуту


if __name__ == "__main__":
    import sys
    if sys.version_info >= (3, 8):
        asyncio.run(main())  # Запуск программы
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())  # Для старых версий Python
