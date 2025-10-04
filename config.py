import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))
DB_NAME = os.getenv("DB_NAME", "academic_works.db")
PLATFORM_REQUISITES = os.getenv("PLATFORM_REQUISITES", "Банковская карта: 0000 0000 0000 0000\nПолучатель: Иван Иванов")
NEWS_CHANNEL = os.getenv("NEWS_CHANNEL")
BOT_USERNAME = os.getenv("BOT_USERNAME")
AI_API_KEY = os.getenv("AI_API_KEY")
AI_API_URL = os.getenv("AI_API_URL")
DB_PATH = os.getenv("DB_NAME", "academic_works.db")
CHANNEL_ID = os.getenv("CHANNEL_ID")