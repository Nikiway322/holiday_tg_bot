import asyncio
import json
import logging
import os
import random
from datetime import date
from pathlib import Path
from typing import List, Optional

import requests
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import Message, BotCommand
from bs4 import BeautifulSoup
from dotenv import load_dotenv
try:
    import cloudscraper  # type: ignore  # helps bypass basic anti-bot pages
except ImportError:
    cloudscraper = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("holiday-bot")

HOLIDAY_URL = "https://kakoysegodnyaprazdnik.ru/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Referer": HOLIDAY_URL,
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}
TOASTS_PATH = Path(__file__).with_name("toasts.json")


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


def parse_holidays(html: str) -> List[str]:
    """Return list of today's holidays using `[itemprop="text"]` nodes."""
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select('[itemprop="text"]')
    holidays = [el.get_text(strip=True) for el in items if el.get_text(strip=True)]

    seen = set()
    unique = []
    for name in holidays:
        if name in seen:
            continue
        seen.add(name)
        unique.append(name)
    return unique


def fetch_holidays(session: Optional[requests.Session] = None) -> List[str]:
    """Fetch holidays from the site synchronously (to be wrapped in a thread).

    Tries plain requests, then falls back to cloudscraper for basic anti-bot pages.
    """
    sess = session or requests.Session()
    sess.headers.update(DEFAULT_HEADERS)

    def _request(client: requests.Session) -> requests.Response:
        resp = client.get(HOLIDAY_URL, timeout=15)
        try:
            resp.raise_for_status()
            return resp
        except Exception:
            logger.error(
                "Failed to fetch %s: status=%s body=%s",
                HOLIDAY_URL,
                getattr(resp, "status_code", "?"),
                getattr(resp, "text", "")[:300],
            )
            raise

    try:
        response = _request(sess)
    except Exception:
        if cloudscraper is None:
            raise
        scraper = cloudscraper.create_scraper()
        scraper.headers.update(DEFAULT_HEADERS)
        response = _request(scraper)

    return parse_holidays(response.text)


def build_toast(holiday: str) -> str:
    template = random.choice(TOAST_TEMPLATES)
    return template.format(holiday=holiday)


async def compose_message() -> str:
    try:
        holidays = await asyncio.to_thread(fetch_holidays)
    except Exception as exc:  
        logger.exception("Failed to fetch holidays: %s", exc)
        return "Не могу узнать праздники — сайт молчит. Попробуйте позже."

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

