"""
Главный файл бота — точка входа.
Инициализирует диспетчер, подключает роутеры, настраивает RedisStorage.
"""
import asyncio
import logging
import signal
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
from redis.asyncio import Redis

from config import (
    BOT_TOKEN,
    LOG_LEVEL,
    REDIS_URL,
    USE_REDIS_STORAGE,
)
from handlers.user.start import router as user_start_router
from handlers.user.booking_steps import router as user_booking_router
from handlers.masseur.actions import router as masseur_actions_router
from google_sheets import init_google_sheets

# Настройка логирования
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_storage():
    """
    Возвращает хранилище FSM.
    Если USE_REDIS_STORAGE=True и есть REDIS_URL — использует RedisStorage.
    Иначе — MemoryStorage (только для разработки!).
    """
    if USE_REDIS_STORAGE and REDIS_URL:
        try:
            redis = Redis.from_url(REDIS_URL, decode_responses=True)
            storage = RedisStorage(redis=redis)
            logger.info("✅ Используется RedisStorage для FSM")
            return storage
        except Exception as e:
            logger.warning(f"⚠️ Не удалось подключиться к Redis ({e}), fallback на MemoryStorage")
    else:
        logger.warning("⚠️ Используется MemoryStorage (сессии потеряются при рестарте!). Для продакшена настройте Redis.")

    return MemoryStorage()


async def on_startup(bot: Bot):
    """Действия при запуске бота."""
    logger.info("🔧 Инициализация Google Sheets...")
    try:
        await init_google_sheets()
        logger.info("✅ Google Sheets успешно инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации Google Sheets: {e}")
        # Не падаем — бот может работать, но записи не сохранятся

    logger.info("🤖 Бот успешно запущен!")
    logger.info("⏳ Бот ожидает сообщений...")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота (graceful shutdown)."""
    logger.info("🛑 Получен сигнал остановки, завершаем работу...")
    # Здесь можно добавить: закрытие соединений, сохранение состояния и т.д.
    logger.info("✅ Бот остановлен корректно")


async def main():
    """Главная функция запуска бота."""
    # Создаём бота и диспетчер
    bot = Bot(token=BOT_TOKEN)
    storage = get_storage()
    dp = Dispatcher(storage=storage)

    # Регистрируем роутеры
    dp.include_router(user_start_router)
    dp.include_router(user_booking_router)
    dp.include_router(masseur_actions_router)

    # Регистрируем startup/shutdown хуки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Graceful shutdown через сигналы
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(dp.shutdown()))

    try:
        # Запускаем поллинг
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # Закрываем сессию бота
        await bot.session.close()
        # Закрываем Redis если использовался
        if hasattr(storage, 'redis') and storage.redis:
            await storage.redis.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.exception(f"💥 Критическая ошибка: {e}")
        sys.exit(1)