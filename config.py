import os

from dotenv import load_dotenv

# Суперподробное логирование для отладки
import logging

logging.basicConfig(level=logging.DEBUG)

aiohttp_logger = logging.getLogger("aiohttp")
aiohttp_logger.setLevel(logging.DEBUG)

# Загрузка переменных из .env файла
load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
# WEATHER_API_URL = ""

if not API_TOKEN:
    raise NameError("API_TOKEN не задан")
