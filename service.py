import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from aiogram import Bot, Dispatcher, types, Router
from aiogram.fsm.storage.memory import MemoryStorage

# Токен бота и ID чата
BOT_TOKEN = "7381459756:AAFcqXCJtFjx-PJpDSVL4Wcs3543nltkzG8"
CHAT_ID = "-1002310647745"

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# URL и класс для парсинга
URL = "https://5cs.fail/en/wheel"
class_name = "rounds-stats__color rounds-stats__color_20x"

# История спинов
spin_history = []


@router.message(lambda message: message.text.lower() == "привет")
async def hello(message: types.Message):
    """Обработчик, который отвечает на сообщение 'Привет'."""
    print(f"Received message: {message.text}")
    await message.answer("Привет! Чем могу помочь?")



def fetch_spin_value():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Для работы в фоновом режиме
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(URL)

    try:
        print("Waiting for the element...")

        # Ожидание появления элемента с увеличенным временем
        element = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".rounds-stats__color.rounds-stats__color_20x"))
        )
        
        # Если элемент найден, выводим его HTML для проверки
        print("Element found. HTML content:")
        print(element.get_attribute("outerHTML"))
        
        spin_value = element.text.strip()
        print(f"Fetched spin value: {spin_value}")
        
        # Преобразуем в целое число, если удается
        try:
            return int(spin_value)
        except ValueError:
            print(f"Invalid spin value: {spin_value}. Cannot convert to integer.")
            return None

    except Exception as e:
        print(f"Error fetching spin value: {e}")
        
        # Сохраняем HTML и скриншот для отладки
        with open("page_source.html", "w", encoding="utf-8") as file:
            file.write(driver.page_source)
        driver.save_screenshot("screenshot.png")
        print("HTML страницы и скриншот сохранены для анализа.")
        
        return None

    finally:
        driver.quit()





last_sent_spin_value = None  

async def check_conditions_and_notify():
    """Функция проверки условий и отправки уведомлений."""
    global spin_history, last_sent_spin_value

    # Получение последнего значения спина
    spin_value = fetch_spin_value()
    if spin_value is None:
        return

    # Обновление истории спинов (хранится только 100 последних значений)
    spin_history.append(spin_value)
    if len(spin_history) > 100:
        spin_history.pop(0)

    print(f"Updated spin history: {spin_history[-10:]}")  # Отладочная информация

    # Если новое значение спина совпадает с последним отправленным, ничего не делаем
    if spin_value == last_sent_spin_value:
        print("Spin value has not changed, skipping notification.")
        return

    # Формируем сообщение в зависимости от значения спина
    if spin_value == 0:
        message = "0 золотых за последние 100 спинов"
    elif spin_value == 1:
        message = "1 золотая за последние 100 спинов"
    elif spin_value == 2:
        message = "2 золотые за последние 100 спинов"
    elif spin_value == 3:
        message = "3 золотые за последние 100 спинов"
    elif spin_value == 4:
        message = "4 золотых за последние 100 спинов"
    elif spin_value == 5:
        message = "5 золотых за последние 100 спинов"
    elif spin_value == 35:
        if 35 not in spin_history[-100:]:
            message = "0 золотых за последние 100 спинов"
        else:
            last_35_index = len(spin_history) - 1 - spin_history[::-1].index(35)
            spins_since_last_35 = len(spin_history) - last_35_index - 1
            if spins_since_last_35 >= 85:
                message = f"С последней золотой 35х прошло {spins_since_last_35} спинов"
            else:
                return  
    else:
        return  

    # Отправляем уведомление и обновляем последнее отправленное значение
    await send_notification(message)
    last_sent_spin_value = spin_value
    print(f"Notification sent: {message}")





async def send_notification(message):
    """Функция для отправки уведомлений в Telegram."""
    for _ in range(3):  # Отправляем сообщение 3 раза
        await bot.send_message(CHAT_ID, message)
        await asyncio.sleep(5) # Delay для отправки 3 сообщений

async def main():
    """Основной цикл программы."""
    # Запускаем проверку условий в фоне
    asyncio.create_task(check_conditions_and_notify_loop())
    # Стартуем бота
    await dp.start_polling(bot)


async def check_conditions_and_notify_loop():
    """Циклическая проверка условий."""
    while True:
        await check_conditions_and_notify()
        await asyncio.sleep(60)  # Проверяем раз в минуту


if __name__ == "__main__":
    import sys
    if sys.version_info >= (3, 8):
        asyncio.run(main())  # Запуск программы
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())  # Для старых версий Python
