"""
Точка входа в приложение
"""

import asyncio
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Tuple, Set

from aiogram import Bot, Dispatcher
from aiogram.types import ContentTypes
from aiogram.utils import executor

from src.config import get_settings
from src.utils.logger import logger
from src.utils.stats import get_stats
from src.vk.api import VKAPI
from src.bot import handlers


def create_bot() -> Tuple[Bot, Dispatcher, VKAPI, Set[int], Path]:
    """
    Инициализация бота и необходимых компонентов

    Returns:
        Tuple: (bot, dispatcher, vk_api, white_list, temp_dir)
    """
    # Загрузка настроек
    settings = get_settings()
    settings.validate()

    # Создание компонентов
    bot = Bot(token=settings.telegram_token)
    dp = Dispatcher(bot)
    vk = VKAPI(
        settings.vk_access_token,
        settings.vk_group_token,
        settings.vk_group_id,
        settings.vk_api_version,
    )

    logger.info(f"Бот инициализирован. White list: {settings.white_list}")

    # Инициализация статистики
    stats = get_stats()

    return bot, dp, vk, settings.white_list, settings.temp_photos_dir


async def cleanup_old_temp_files(temp_dir: Path, max_age_hours: int = 1) -> None:
    """
    Удаляет временные файлы старше указанного возраста

    Args:
        temp_dir: Директория с временными файлами
        max_age_hours: Максимальный возраст файлов в часах
    """
    if not temp_dir.exists():
        return

    now = datetime.now().timestamp()
    removed = 0

    for file in temp_dir.glob("*.jpg"):
        try:
            age = now - file.stat().st_mtime
            if age > max_age_hours * 3600:
                file.unlink()
                removed += 1
        except Exception as e:
            logger.error(f"Ошибка удаления {file}: {e}")

    if removed > 0:
        logger.info(f"🧹 Очищено {removed} старых временных файлов")


async def on_startup(dp: Dispatcher) -> None:
    """Действия при запуске бота"""
    logger.info("Бот запущен и готов к работе")

    settings = get_settings()

    # Настройка меню команд бота
    await handlers.setup_bot_commands(dp.bot)

    # Очистка старых файлов при запуске
    await cleanup_old_temp_files(settings.temp_photos_dir, settings.cleanup_age_hours)

    # Запуск периодической очистки
    async def periodic_cleanup():
        while True:
            await asyncio.sleep(settings.cleanup_interval_hours * 3600)
            await cleanup_old_temp_files(
                settings.temp_photos_dir, settings.cleanup_age_hours
            )

    asyncio.create_task(periodic_cleanup())


async def on_shutdown(dp: Dispatcher) -> None:
    """Действия при остановке бота"""
    logger.info("Завершение работы...")

    settings = get_settings()
    stats = get_stats()

    # Вывод финальной статистики
    logger.info(stats.get_report())

    # Очистка временных файлов
    if settings.temp_photos_dir.exists():
        removed = 0
        for file in settings.temp_photos_dir.glob("*"):
            try:
                file.unlink()
                removed += 1
            except Exception as e:
                logger.error(f"Ошибка удаления {file}: {e}")
        if removed > 0:
            logger.info(f"🧹 Удалено {removed} временных файлов")

    await dp.storage.close()
    await dp.storage.wait_closed()
    logger.info("Graceful shutdown завершен")


def main() -> None:
    """Основная функция запуска приложения"""

    def shutdown_handler(signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        if not handlers.is_shutting_down():
            handlers.set_shutting_down(True)
            logger.info(f"Получен сигнал {signum}, инициирую graceful shutdown...")
            sys.exit(0)

    try:
        logger.info("=" * 50)
        logger.info("Запуск приложения")
        logger.info("=" * 50)

        # Регистрация обработчиков сигналов
        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

        bot, dp, vk, white_list, temp_dir = create_bot()

        # Регистрация обработчиков команд
        dp.register_message_handler(handlers.send_welcome, commands=["start", "help"])
        dp.register_message_handler(handlers.send_stats, commands=["stats"])
        )
        dp.register_message_handler(
            lambda message: handlers.handle_photo(
                message, bot, vk, white_list, temp_dir
            ),
            content_types=ContentTypes.PHOTO,
        )

        # Запуск polling
        executor.start_polling(
            dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown
        )

    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал остановки")
        handlers.set_shutting_down(True)
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}", exc_info=True)
        raise
    finally:
        if handlers.is_shutting_down():
            logger.info("Завершение работы приложения...")
        logger.info("Приложение завершено")


if __name__ == "__main__":
    main()
