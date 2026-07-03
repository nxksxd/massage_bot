"""
Конфигурация для massage_bot
"""
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# ============================================================
# TELEGRAM
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MASSEUR_ID = int(os.getenv("MASSEUR_ID", "0"))  # Telegram ID массажиста

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не установлен! Добавьте его в .env файл")

# ============================================================
# GOOGLE SHEETS
# ============================================================
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE", "credentials.json")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")

if not SPREADSHEET_ID:
    raise ValueError("❌ SPREADSHEET_ID не установлен! Добавьте его в .env файл")

# ============================================================
# GOOGLE SHEETS КЕШИРОВАНИЕ И ОПТИМИЗАЦИЯ
# ============================================================
# Время кеша Google Sheet подключения (сек)
GOOGLE_SHEET_CACHE_TTL = int(os.getenv("GOOGLE_SHEET_CACHE_TTL", "300"))

# Максимальное количество retry попыток для Google Sheets
GOOGLE_SHEETS_MAX_RETRIES = int(os.getenv("GOOGLE_SHEETS_MAX_RETRIES", "3"))

# Таймаут для операций с Google Sheets (сек)
GOOGLE_SHEETS_TIMEOUT = int(os.getenv("GOOGLE_SHEETS_TIMEOUT", "30"))

# Базовая задержка между retry попытками (сек)
GOOGLE_SHEETS_RETRY_DELAY = float(os.getenv("GOOGLE_SHEETS_RETRY_DELAY", "1"))

# ============================================================
# ЛОГИРОВАНИЕ
# ============================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ============================================================
# ВАЛИДАЦИЯ ДАННЫХ
# ============================================================
# Минимальная длина имени
MIN_NAME_LENGTH = 2
# Максимальная длина имени
MAX_NAME_LENGTH = 100

# Формат даты
DATE_FORMAT = "%d.%m.%Y"
TIME_FORMAT = "%H:%M"

# Регулярные выражения для валидации
VALID_PHONE_PATTERN = r"^\d{10,15}$"
VALID_TIME_PATTERN = r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
VALID_DATE_PATTERN = r"^\d{2}\.\d{2}\.\d{4}$"

