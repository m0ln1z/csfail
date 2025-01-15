import os
import json
import logging
import asyncio
import time
import gc

from requests_html import AsyncHTMLSession

from aiogram import Bot, Dispatcher, types, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

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

def load_state():
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

# Асинхронная версия функции для получения spinValue
async def fetchSpinValue():
    """
    Использует AsyncHTMLSession, чтобы открыть страницу
    и получить spinValue. Если не удаётся, возвращает None.
    """
    try:
        asession = AsyncHTMLSession()
        r = await asession.get(url)

        # Если сайт динамически подгружает данные через JS — делаем рендер
        await r.html.arender(timeout=20, sleep=1)  # рендерим JS (если нужно)

        element = r.html.find(f".{className.replace(' ', '.')}", first=True)
        if element:
            spinValue = element.text.strip()
            return int(spinValue) if spinValue.isdigit() else None

        return None

    except Exception as e:
        logging.error(f"Ошибка в requests_html: {e}")
        return None


async def checkConditionsAndNotify():
    global spinHistory, lastSentSpinValue, lastNotifiedSpinValue, unchangedSpinValueCount

    spinValue = await fetchSpinValue()
    if spinValue is None:
        return

    spinHistory.append(spinValue)
    if len(spinHistory) > 100:
        spinHistory.pop(0)

    logging.info(f"Обновление истории спинов: {spinHistory[-10:]}")

    # Пример логики: если текущее значение <= предыдущего — увеличиваем счётчик, иначе сбрасываем.
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
            alertMessage = f"Значение {spinValue} повторяется уже 85 раз подряд!"
            await sendNotification(alertMessage)
            logging.info(f"Уведомление о повторении отправлено: {alertMessage}")
            unchangedSpinValueCount = 0
    else:
        unchangedSpinValueCount = 0

    # Уведомление при каждом новом spinValue (или изменении).
    if spinValue != lastNotifiedSpinValue:
        message = f"{spinValue} золотых за последние 100 спинов"
        await sendNotification(message)
        lastNotifiedSpinValue = spinValue
        logging.info(f"Уведомление отправлено: {message}")

    lastSentSpinValue = spinValue

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
            gc.collect()
        await asyncio.sleep(60)

async def main():
    load_state()
    asyncio.create_task(checkConditionsAndNotifyLoop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    import sys

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