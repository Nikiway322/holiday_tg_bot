import asyncio
import json
import logging
import os
import random
from datetime import date
from pathlib import Path
from typing import Dict, List

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import Message, BotCommand
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("holiday-bot")

TOASTS_PATH = Path(__file__).with_name("toasts.json")
HOLIDAYS_PATH = Path(__file__).with_name("holidays.json")


def load_toasts() -> List[str]:
    try:
        data = json.loads(TOASTS_PATH.read_text(encoding="utf-8"))
        return [t for t in data if isinstance(t, str) and t.strip()]
    except FileNotFoundError:
        logger.error("toasts.json not found")
        return []
    except Exception as exc: 
        logger.error("Failed to load toasts: %s", exc)
        return []


TOAST_TEMPLATES = load_toasts()


def load_holidays() -> Dict[str, List[str]]:
    """Load holidays grouped by MM-DD from local JSON file."""
    try:
        raw = json.loads(HOLIDAYS_PATH.read_text(encoding="utf-8"))
        data: Dict[str, List[str]] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            key = item.get("date")
            value = item.get("holidays")
            if isinstance(key, str) and isinstance(value, list):
                holidays = [h for h in value if isinstance(h, str) and h.strip()]
                if holidays:
                    data[key] = holidays
        return data
    except FileNotFoundError:
        logger.error("holidays.json not found")
        return {}
    except Exception as exc:
        logger.error("Failed to load holidays: %s", exc)
        return {}


HOLIDAYS_BY_DATE = load_holidays()


def build_toast(holiday: str) -> str:
    template = random.choice(TOAST_TEMPLATES)
    return template.format(holiday=holiday)


async def compose_message() -> str:
    if not HOLIDAYS_BY_DATE:
        return "Не могу загрузить праздники — файл отсутствует или поврежден."

    today_key = date.today().strftime("%m-%d")
    holidays = HOLIDAYS_BY_DATE.get(today_key, [])

    if not holidays:
        return "Сегодня не нашел праздников. Но повод придумать несложно 😉"

    today = date.today().strftime("%d.%m.%Y")
    holiday = random.choice(holidays)
    toast = build_toast(holiday)

    return (
        f"Сегодня {today} — {holiday}\n\n"
        f"\n{toast}"
    )


async def handle_start(message: Message) -> None:
    await message.answer(
        "Привет! Я подскажу, какой сегодня праздник.\n"
        "Команда: /povod (алиас /holiday).\n"
        "В группе отвечаю только на эти команды, чтобы не шуметь.",
    )


async def handle_prazdnik(message: Message) -> None:
    reply = await compose_message()
    await message.reply(reply)


async def handle_private_chat(message: Message) -> None:
    reply = await compose_message()
    await message.reply(reply)


async def main() -> None:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Environment variable BOT_TOKEN is required")

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()


    await bot.set_my_commands(
        commands=[
            BotCommand(command="start", description="О боте"),
            BotCommand(command="povod", description="Показать праздник и тост"),
        ]
    )

    dp.message.register(handle_start, Command("start"))
    dp.message.register(handle_prazdnik, Command(commands=["povod", "holiday"]))
    dp.message.register(handle_private_chat, F.chat.type == "private")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

