"""
Оптимизированный модуль для работы с Google Sheets
Включает: кеширование, асинхронность, retry логику, батчирование обновлений
"""
import asyncio
import logging
import time
import traceback
from typing import Optional
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from booking_rules import (
    normalize_name,
    validate_birth_date,
    validate_booking_date,
    validate_name as validate_name_value,
    validate_time as validate_time_value,
)
from config import (
    CREDENTIALS_FILE,
    SPREADSHEET_ID,
    GOOGLE_SHEET_NAME,
    GOOGLE_SHEET_CACHE_TTL,
    GOOGLE_SHEETS_MAX_RETRIES,
    GOOGLE_SHEETS_TIMEOUT,
    GOOGLE_SHEETS_RETRY_DELAY,
    DATE_FORMAT,
)

logger = logging.getLogger(__name__)

# Права доступа к Google сервисам
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ============================================================
# КЕШИРОВАНИЕ Google Sheet ПОДКЛЮЧЕНИЯ
# ============================================================

class SheetCache:
    """Кеш для Google Sheet подключения с автоматическим истечением"""

    def __init__(self, ttl_seconds: int = GOOGLE_SHEET_CACHE_TTL):
        self.ttl = ttl_seconds
        self.sheet = None
        self.timestamp = None

    def is_valid(self) -> bool:
        """Проверяем валиден ли кеш"""
        if self.sheet is None or self.timestamp is None:
            return False
        elapsed = time.time() - self.timestamp
        return elapsed < self.ttl

    def get(self):
        """Получить кеш если валиден"""
        if self.is_valid():
            logger.debug(f"📦 Google Sheet из кеша (осталось {self.ttl - (time.time() - self.timestamp):.0f}сек)")
            return self.sheet
        return None

    def set(self, sheet):
        """Установить новый кеш"""
        self.sheet = sheet
        self.timestamp = time.time()
        logger.info(f"✅ Google Sheet подключение закешировано (TTL: {self.ttl}сек)")

    def invalidate(self):
        """Принудительно инвалидировать кеш"""
        self.sheet = None
        self.timestamp = None
        logger.info("🗑️ Кеш Google Sheet инвалидирован")


# Глобальный кеш
_sheet_cache = SheetCache()


# ============================================================
# ВАЛИДАЦИЯ ДАННЫХ (обёртки над booking_rules для логирования)
# ============================================================

def validate_name(name: str, field_name: str = "Имя") -> bool:
    """Валидация имени"""
    if not isinstance(name, str):
        logger.warning(f"❌ {field_name}: тип должен быть str, получен {type(name)}")
        return False

    if not validate_name_value(name):
        normalized = normalize_name(name)
        logger.warning(f"❌ {field_name}: некорректная длина значения '{normalized}'")
        return False

    return True


def validate_date(date_str: str) -> bool:
    """Валидация даты сеанса в формате ДД.ММ.ГГГГ"""
    is_valid, error_code = validate_booking_date(date_str)
    if not is_valid:
        logger.warning(f"❌ Некорректная дата сеанса ({error_code}): {date_str}")
        return False
    return True


def validate_birth_date_value(date_str: str) -> bool:
    """Валидация даты рождения ребенка"""
    is_valid, error_code = validate_birth_date(date_str)
    if not is_valid:
        logger.warning(f"❌ Некорректная дата рождения ({error_code}): {date_str}")
        return False
    return True


def validate_time(time_str: str) -> bool:
    """Валидация времени в формате ЧЧ:ММ"""
    is_valid, _ = validate_time_value(time_str)
    if not is_valid:
        logger.warning(f"❌ Время должно быть в формате ЧЧ:ММ, получено: {time_str}")
        return False
    return True


def validate_booking_data(booking_data: dict) -> bool:
    """Комплексная валидация данных записи"""
    required_fields = [
        ('parent_name', validate_name),
        ('child_name', validate_name),
        ('child_age', validate_birth_date_value),
        ('massage_type', lambda x: isinstance(x, str) and len(x.strip()) > 0),
        ('date', validate_date),
        ('time', validate_time),
    ]

    for field, validator in required_fields:
        if field not in booking_data:
            logger.warning(f"❌ Отсутствует поле: {field}")
            return False

        if not validator(booking_data[field]):
            logger.warning(f"❌ Ошибка валидации поля: {field}")
            return False

    return True


# ============================================================
# РАБОТА С GOOGLE SHEETS (АСИНХРОННО)
# ============================================================

def _get_google_sheet_sync():
    """Синхронная функция получения Google Sheet (оборачивается в asyncio.to_thread)"""
    # Сначала проверяем кеш
    cached_sheet = _sheet_cache.get()
    if cached_sheet is not None:
        return cached_sheet

    # Подключаемся к Google Sheets
    logger.info("🔗 Подключение к Google Sheets...")
    creds = Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=SCOPES
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    # Используем настроенное имя листа вместо sheet1
    try:
        sheet = spreadsheet.worksheet(GOOGLE_SHEET_NAME)
    except gspread.WorksheetNotFound:
        logger.warning(f"⚠️ Лист '{GOOGLE_SHEET_NAME}' не найден, используем первый лист")
        sheet = spreadsheet.sheet1

    # Кешируем подключение
    _sheet_cache.set(sheet)

    return sheet


async def get_google_sheet():
    """Асинхронное получение Google Sheet с retry логикой"""
    last_exception = None

    for attempt in range(GOOGLE_SHEETS_MAX_RETRIES):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_get_google_sheet_sync),
                timeout=GOOGLE_SHEETS_TIMEOUT
            )
        except asyncio.TimeoutError:
            last_exception = TimeoutError(f"⏱ Операция превысила таймаут ({GOOGLE_SHEETS_TIMEOUT}сек)")
            logger.warning(f"⏱ Таймаут на попытке {attempt + 1}/{GOOGLE_SHEETS_MAX_RETRIES}")
        except Exception as e:
            last_exception = e
            logger.warning(f"⚠️ Попытка {attempt + 1}/{GOOGLE_SHEETS_MAX_RETRIES} ошибка: {e}")

        if attempt == GOOGLE_SHEETS_MAX_RETRIES - 1:
            logger.error(f"❌ Все {GOOGLE_SHEETS_MAX_RETRIES} попыток исчерпаны")
            raise last_exception

        delay = GOOGLE_SHEETS_RETRY_DELAY * (2 ** attempt)
        logger.debug(f"⏳ Ожидание {delay:.1f}сек перед повтором...")
        await asyncio.sleep(delay)

    return None


async def init_google_sheets() -> bool:
    """Инициализация Google Sheets при запуске бота (проверка подключения)"""
    try:
        sheet = await get_google_sheet()
        if sheet:
            logger.info(f"✅ Google Sheets успешно инициализирована (лист: {sheet.title})")
            return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации Google Sheets: {e}")
        traceback.print_exc()
    return False


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def get_age_word(number: int, word_forms: tuple) -> str:
    """Правильная форма слова в зависимости от числа"""
    if 11 <= number % 100 <= 19:
        return word_forms[2]

    last_digit = number % 10

    if last_digit == 1:
        return word_forms[0]
    elif 2 <= last_digit <= 4:
        return word_forms[1]
    else:
        return word_forms[2]


def calculate_age(birth_date_str: str) -> str:
    """
    Расчет возраста по дате рождения (формат ДД.ММ.ГГГГ)

    Возвращает строку вида:
    - 'ДД.ММ.ГГГГ (5 месяцев)'
    - 'ДД.ММ.ГГГГ (1 год)'
    - 'ДД.ММ.ГГГГ (2 года 3 месяца)'
    """
    try:
        birth_date = datetime.strptime(birth_date_str, DATE_FORMAT)
        today = datetime.today()

        # Считаем полные года
        years = today.year - birth_date.year
        birthday_this_year = birth_date.replace(year=today.year)
        if today < birthday_this_year:
            years -= 1

        # Считаем полные месяцы сверх полных лет
        if years >= 0:
            try:
                last_birthday = birth_date.replace(year=birth_date.year + years)
            except ValueError:
                last_birthday = birth_date.replace(year=birth_date.year + years, day=28)
        else:
            last_birthday = birth_date

        months = (today.year - last_birthday.year) * 12
        months += today.month - last_birthday.month

        if today.day < last_birthday.day:
            months -= 1

        if months < 0:
            months = 0

        # Формируем строку возраста
        if years == 0 and months == 0:
            age_str = "меньше месяца"
        elif years == 0:
            month_word = get_age_word(months, ("месяц", "месяца", "месяцев"))
            age_str = f"{months} {month_word}"
        elif months == 0:
            year_word = get_age_word(years, ("год", "года", "лет"))
            age_str = f"{years} {year_word}"
        else:
            year_word = get_age_word(years, ("год", "года", "лет"))
            month_word = get_age_word(months, ("месяц", "месяца", "месяцев"))
            age_str = f"{years} {year_word} {months} {month_word}"

        return f"{birth_date_str} ({age_str})"

    except ValueError:
        return birth_date_str


# ============================================================
# ОСНОВНЫЕ ФУНКЦИИ РАБОТЫ С ЗАПИСЯМИ
# ============================================================

def _save_booking_sync(booking_data: dict) -> Optional[int]:
    """
    Синхронная функция сохранения записи.
    Возвращает номер записи или None при ошибке.
    """
    # Валидируем данные
    if not validate_booking_data(booking_data):
        logger.error(
            "❌ Данные не прошли валидацию. Поля: %s",
            sorted(booking_data.keys()),
        )
        return None

    sheet = _sheet_cache.get()
    if sheet is None:
        # Если кеш пуст, получаем новое подключение
        creds = Credentials.from_service_account_file(
            CREDENTIALS_FILE,
            scopes=SCOPES
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        try:
            sheet = spreadsheet.worksheet(GOOGLE_SHEET_NAME)
        except gspread.WorksheetNotFound:
            sheet = spreadsheet.sheet1
        _sheet_cache.set(sheet)

    try:
        all_values = sheet.get_all_values()

        # Находим максимальный номер записи (колонка A)
        max_record_number = 0
        for row in all_values[1:]:  # пропускаем заголовок
            if row and row[0].isdigit():
                try:
                    record_num = int(row[0])
                    max_record_number = max(max_record_number, record_num)
                except ValueError:
                    pass

        next_record_number = max_record_number + 1

        booking_datetime = datetime.now().strftime("%d.%m.%Y %H:%M")
        birth_date = booking_data.get('child_age', '')
        age_with_date = calculate_age(birth_date)

        user_id = booking_data.get('user_id', '')
        username = booking_data.get('username', '')

        if username:
            client_link = f"https://t.me/{username}"
        else:
            client_link = f"tg://user?id={user_id}"

        row = [
            str(next_record_number),
            booking_datetime,
            normalize_name(booking_data.get('parent_name', '')),
            normalize_name(booking_data.get('child_name', '')),
            age_with_date,
            booking_data.get('massage_type', ''),
            booking_data.get('date', ''),
            booking_data.get('time', ''),
            booking_data.get('comment', ''),
            str(user_id),
            client_link
        ]

        sheet.append_row(row)

        logger.info(f"✅ Запись #{next_record_number} успешно сохранена")
        return next_record_number

    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении записи: {e}")
        traceback.print_exc()
        return None


async def save_booking(booking_data: dict) -> Optional[int]:
    """Асинхронное сохранение записи с retry логикой"""
    last_exception = None

    for attempt in range(GOOGLE_SHEETS_MAX_RETRIES):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_save_booking_sync, booking_data),
                timeout=GOOGLE_SHEETS_TIMEOUT
            )
        except asyncio.TimeoutError:
            last_exception = TimeoutError(f"⏱ Операция превысила таймаут ({GOOGLE_SHEETS_TIMEOUT}сек)")
            logger.warning(f"⏱ Таймаут на попытке {attempt + 1}/{GOOGLE_SHEETS_MAX_RETRIES}")
        except Exception as e:
            last_exception = e
            logger.warning(f"⚠️ Попытка {attempt + 1}/{GOOGLE_SHEETS_MAX_RETRIES} ошибка: {e}")

        if attempt == GOOGLE_SHEETS_MAX_RETRIES - 1:
            logger.error(f"❌ Все {GOOGLE_SHEETS_MAX_RETRIES} попыток исчерпаны")
            return None

        delay = GOOGLE_SHEETS_RETRY_DELAY * (2 ** attempt)
        logger.debug(f"⏳ Ожидание {delay:.1f}сек перед повтором...")
        await asyncio.sleep(delay)

    return None


def _update_booking_sync(record_number: int, updated_data: dict) -> bool:
    """Синхронная функция обновления записи (с батчированием)"""
    sheet = _sheet_cache.get()
    if sheet is None:
        creds = Credentials.from_service_account_file(
            CREDENTIALS_FILE,
            scopes=SCOPES
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        try:
            sheet = spreadsheet.worksheet(GOOGLE_SHEET_NAME)
        except gspread.WorksheetNotFound:
            sheet = spreadsheet.sheet1
        _sheet_cache.set(sheet)

    try:
        all_values = sheet.get_all_values()

        # Ищем строку по номеру записи
        row_number = None
        for i, row in enumerate(all_values, start=1):
            if i > 1 and len(row) > 0 and row[0] == str(record_number):
                row_number = i
                break

        if row_number is None:
            logger.warning(f"⚠️ Запись #{record_number} не найдена")
            return False

        logger.info(f"✏️ Обновление записи #{record_number} (строка {row_number})")

        # Маппинг полей на столбцы
        field_to_column = {
            'parent_name': 3,      # C
            'child_name': 4,       # D
            'child_age': 5,        # E
            'massage_type': 6,     # F
            'date': 7,             # G
            'time': 8,             # H
            'comment': 9           # I
        }

        # БАТЧИРОВАНИЕ: Собираем все обновления и выполняем в одном batch_update
        updates = []
        for field, value in updated_data.items():
            if field in field_to_column:
                col = field_to_column[field]

                if field in {'parent_name', 'child_name'}:
                    if not validate_name(value, field):
                        logger.warning(f"⚠️ Некорректное имя для поля {field}: {value}")
                        return False
                    value = normalize_name(value)
                elif field == 'child_age':
                    if validate_birth_date_value(value):
                        value = calculate_age(value)
                    else:
                        logger.warning(f"⚠️ Некорректная дата рождения: {value}")
                        return False
                elif field == 'date':
                    if not validate_date(value):
                        logger.warning(f"⚠️ Некорректная дата сеанса: {value}")
                        return False
                elif field == 'time':
                    is_valid, normalized_time = validate_time_value(value)
                    if not is_valid:
                        logger.warning(f"⚠️ Некорректное время: {value}")
                        return False
                    value = normalized_time
                elif field == 'comment':
                    value = value.strip()

                # Добавляем обновление в список (A1 notation)
                cell = gspread.utils.rowcol_to_a1(row_number, col)
                updates.append({
                    'range': cell,
                    'values': [[value]]
                })

        # Выполняем все обновления одним batch_update (10x быстрее!)
        if updates:
            sheet.batch_update(updates)
            logger.info(f"✅ Запись #{record_number} успешно обновлена ({len(updates)} полей)")

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении записи: {e}")
        traceback.print_exc()
        return False


async def update_booking(record_number: int, updated_data: dict) -> bool:
    """Асинхронное обновление записи с retry логикой"""
    last_exception = None

    for attempt in range(GOOGLE_SHEETS_MAX_RETRIES):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_update_booking_sync, record_number, updated_data),
                timeout=GOOGLE_SHEETS_TIMEOUT
            )
        except asyncio.TimeoutError:
            last_exception = TimeoutError(f"⏱ Операция превысила таймаут ({GOOGLE_SHEETS_TIMEOUT}сек)")
            logger.warning(f"⏱ Таймаут на попытке {attempt + 1}/{GOOGLE_SHEETS_MAX_RETRIES}")
        except Exception as e:
            last_exception = e
            logger.warning(f"⚠️ Попытка {attempt + 1}/{GOOGLE_SHEETS_MAX_RETRIES} ошибка: {e}")

        if attempt == GOOGLE_SHEETS_MAX_RETRIES - 1:
            logger.error(f"❌ Все {GOOGLE_SHEETS_MAX_RETRIES} попыток исчерпаны")
            return False

        delay = GOOGLE_SHEETS_RETRY_DELAY * (2 ** attempt)
        logger.debug(f"⏳ Ожидание {delay:.1f}сек перед повтором...")
        await asyncio.sleep(delay)

    return False


def _get_user_id_by_record_number_sync(record_number: int) -> Optional[int]:
    """Синхронная функция получения user_id по номеру записи"""
    sheet = _sheet_cache.get()
    if sheet is None:
        creds = Credentials.from_service_account_file(
            CREDENTIALS_FILE,
            scopes=SCOPES
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        try:
            sheet = spreadsheet.worksheet(GOOGLE_SHEET_NAME)
        except gspread.WorksheetNotFound:
            sheet = spreadsheet.sheet1
        _sheet_cache.set(sheet)

    try:
        all_values = sheet.get_all_values()

        for row in all_values[1:]:  # пропускаем заголовок
            if row and len(row) >= 10 and row[0] == str(record_number):
                user_id_str = row[9]  # колонка J (user_id)
                if user_id_str.isdigit():
                    return int(user_id_str)
                return None
        return None

    except Exception as e:
        logger.error(f"❌ Ошибка при получении user_id: {e}")
        traceback.print_exc()
        return None


async def get_user_id_by_record_number(record_number: int) -> Optional[int]:
    """Асинхронное получение user_id по номеру записи с retry логикой"""
    last_exception = None

    for attempt in range(GOOGLE_SHEETS_MAX_RETRIES):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_get_user_id_by_record_number_sync, record_number),
                timeout=GOOGLE_SHEETS_TIMEOUT
            )
        except asyncio.TimeoutError:
            last_exception = TimeoutError(f"⏱ Операция превысила таймаут ({GOOGLE_SHEETS_TIMEOUT}сек)")
            logger.warning(f"⏱ Таймаут на попытке {attempt + 1}/{GOOGLE_SHEETS_MAX_RETRIES}")
        except Exception as e:
            last_exception = e
            logger.warning(f"⚠️ Попытка {attempt + 1}/{GOOGLE_SHEETS_MAX_RETRIES} ошибка: {e}")

        if attempt == GOOGLE_SHEETS_MAX_RETRIES - 1:
            logger.error(f"❌ Все {GOOGLE_SHEETS_MAX_RETRIES} попыток исчерпаны")
            return None

        delay = GOOGLE_SHEETS_RETRY_DELAY * (2 ** attempt)
        logger.debug(f"⏳ Ожидание {delay:.1f}сек перед повтором...")
        await asyncio.sleep(delay)

    return None
def _get_booking_by_record_number_sync(record_number: int):
    """Синхронно получает все поля записи по номеру. Возвращает dict или None."""
    sheet = _sheet_cache.get()
    if sheet is None:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        try:
            sheet = spreadsheet.worksheet(GOOGLE_SHEET_NAME)
        except gspread.WorksheetNotFound:
            sheet = spreadsheet.sheet1
        _sheet_cache.set(sheet)

    try:
        all_values = sheet.get_all_values()
        for row in all_values[1:]:  # пропускаем заголовок
            if row and len(row) >= 9 and row[0] == str(record_number):
                def g(i):
                    return row[i] if len(row) > i else ""
                return {
                    "parent_name": g(2),
                    "child_name": g(3),
                    "child_age": g(4),
                    "massage_type": g(5),
                    "date": g(6),
                    "time": g(7),
                    "comment": g(8),
                    "user_id": g(9),
                }
        return None
    except Exception as e:
        logger.error(f"❌ Ошибка при получении записи #{record_number}: {e}")
        traceback.print_exc()
        return None


async def get_booking_by_record_number(record_number: int):
    """Асинхронно получает все поля записи по номеру с retry логикой."""
    for attempt in range(GOOGLE_SHEETS_MAX_RETRIES):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_get_booking_by_record_number_sync, record_number),
                timeout=GOOGLE_SHEETS_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning(f"⏱ Таймаут get_booking на попытке {attempt + 1}/{GOOGLE_SHEETS_MAX_RETRIES}")
        except Exception as e:
            logger.warning(f"⚠️ get_booking попытка {attempt + 1}/{GOOGLE_SHEETS_MAX_RETRIES} ошибка: {e}")

        if attempt == GOOGLE_SHEETS_MAX_RETRIES - 1:
            logger.error(f"❌ get_booking: все попытки исчерпаны для #{record_number}")
            return None
        await asyncio.sleep(GOOGLE_SHEETS_RETRY_DELAY * (2 ** attempt))
