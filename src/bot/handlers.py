"""
Обработчики команд и сообщений Telegram бота
"""

from pathlib import Path
from typing import Set

from aiogram import Bot, types
from aiogram.types import BotCommand

from src.utils.logger import logger
from src.utils.stats import get_stats
from src.utils.file_validator import prepare_file_for_upload
from src.vk.api import VKAPI
from src.config.constants import (
    BOT_WELCOME_MESSAGE,
    BOT_NO_ACCESS_MESSAGE,
    BOT_SHUTTING_DOWN_MESSAGE,
    BOT_FILE_NOT_READY_MESSAGE,
    BOT_UPLOADING_MESSAGE,
    BOT_ERROR_MESSAGE,
    BOT_SUCCESS_MESSAGE,
)


# Глобальный флаг для graceful shutdown
_is_shutting_down = False


def set_shutting_down(value: bool) -> None:
    """Установить флаг graceful shutdown"""
    global _is_shutting_down
    _is_shutting_down = value


def is_shutting_down() -> bool:
    """Проверить флаг graceful shutdown"""
    return _is_shutting_down


async def setup_bot_commands(bot: Bot) -> None:
    """
    Настройка меню команд бота

    Args:
        bot: Экземпляр бота
    """
    commands = [
        BotCommand(command="start", description="🚀 Начать работу с ботом"),
        BotCommand(command="help", description="❓ Помощь и инструкция"),
        BotCommand(command="stats", description="📊 Статистика работы бота"),
    ]

    await bot.set_my_commands(commands)
    logger.info("Меню команд бота настроено")


async def send_welcome(message: types.Message) -> None:
    """
    Обработчик команды /start и /help

    Args:
        message: Сообщение от пользователя
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username or "без username"

    logger.info(
        f"Вызвана команда /{message.text.strip('/')} "
        f"для user_id={user_id} (chat_id={chat_id}, username=@{username})"
    )

    await message.reply(BOT_WELCOME_MESSAGE)


async def send_stats(message: types.Message) -> None:
    """
    Обработчик команды /stats
    Отправляет детальную статистику работы бота

    Args:
        message: Сообщение от пользователя
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username or "без username"

    logger.info(
        f"Вызвано получение статистики бота "
        f"для user_id={user_id} (chat_id={chat_id}, username=@{username})"
    )

    stats = get_stats()
    stats_dict = stats.get_dict()

    # Время по МСК
    msk_time = stats.get_current_msk_time()

    report_lines = [
        "📊 *СТАТИСТИКА БОТА*",
        "",
        f"🕐 Время: {msk_time.strftime('%d.%m.%Y %H:%M')}",
        f"⏱ Работает: {stats_dict['uptime']['formatted']}",
        "",
        "📅 *ЗА СУТКИ:*",
        f"📝 Получено: {stats_dict['daily']['total']}",
        f"✅ Успешно: {stats_dict['daily']['success']}",
        f"❌ Ошибок: {stats_dict['daily']['errors']}",
    ]

    # Добавляем success rate только если были посты
    if stats_dict["daily"]["total"] > 0:
        report_lines.append(f"📈 Success: {stats_dict['daily']['success_rate']:.1f}%")

    report_lines.extend(
        [
            "",
            "📊 *ЗА ВСЁ ВРЕМЯ:*",
            f"📝 Обработано: {stats_dict['total']['total']}",
            f"✅ Успешно: {stats_dict['total']['success']}",
            f"❌ Ошибок: {stats_dict['total']['errors']}",
        ]
    )

    # Добавляем success rate только если были посты
    if stats_dict["total"]["total"] > 0:
        report_lines.append(f"📈 Success: {stats_dict['total']['success_rate']:.1f}%")

        # Оценка качества работы
        success_rate = stats_dict["total"]["success_rate"]
        if success_rate >= 99:
            quality = "🌟 Отлично!"
        elif success_rate >= 95:
            quality = "✅ Хорошо"
        elif success_rate >= 90:
            quality = "⚠️ Норма"
        else:
            quality = "❌ Нужна проверка"

        report_lines.extend(
            [
                "",
                f"Оценка: {quality}",
            ]
        )

    await message.answer("\n".join(report_lines), parse_mode="Markdown")


async def handle_photo(
    message: types.Message, bot: Bot, vk: VKAPI, white_list: Set[int], temp_dir: Path
) -> None:
    """
    Обработчик фотографий из Telegram

    Args:
        message: Сообщение с фото
        bot: Экземпляр бота
        vk: Экземпляр VK API
        white_list: Список разрешенных chat_id
        temp_dir: Директория для временных файлов
    """
    # Проверка graceful shutdown
    if _is_shutting_down:
        await message.reply(BOT_SHUTTING_DOWN_MESSAGE)
        logger.warning(f"Отклонен запрос от {message.chat.id}: бот завершает работу")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.username or "без username"

    # Проверка white list
    if chat_id not in white_list:
        logger.warning(
            f"Попытка отправки от неразрешенного чата: "
            f"user_id={user_id} (chat_id={chat_id}, username=@{username})"
        )
        await message.reply(BOT_NO_ACCESS_MESSAGE)
        return

    stats = get_stats()

    try:
        # Получение данных о фото
        text = message.caption or ""
        photo = message.photo[-1]  # Берем фото максимального качества
        file_id = photo.file_id

        logger.info(
            f"Получено фото от user_id={user_id} "
            f"(chat_id={chat_id}, username=@{username}), file_id: {file_id}"
        )

        # Получение информации о файле
        file = await bot.get_file(file_id)
        file_path = file.file_path

        # Создание временной директории если не существует
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Формирование локального пути
        local_filename = temp_dir / f"{file_id}.jpg"

        # Загрузка файла
        await file.download(destination=str(local_filename))
        logger.debug(f"Файл загружен: {local_filename}")

        # Комплексная проверка готовности файла
        if not await prepare_file_for_upload(str(local_filename)):
            await message.reply(BOT_FILE_NOT_READY_MESSAGE)
            stats.increment_error()
            return

        # Отправка уведомления пользователю
        status_msg = await message.reply(BOT_UPLOADING_MESSAGE)

        # Публикация в ВК
        result = await vk.create_post_from_wall(str(local_filename), text)

        if result and "response" in result:
            post_id = result["response"].get("post_id")
            success_message = BOT_SUCCESS_MESSAGE.format(post_id=post_id)
            await status_msg.edit_text(success_message)

            logger.info(
                f"Успешная публикация поста {post_id} "
                f"от user_id={user_id} (chat_id={chat_id})"
            )

            # Статистика успеха
            stats.increment_success()

            # Каждые N успешных постов - выводим статистику
            if stats.should_log_stats():
                logger.info(stats.get_log_stats())
        else:
            await status_msg.edit_text(BOT_ERROR_MESSAGE)
            logger.error(
                f"Не удалось опубликовать пост от user_id={user_id} (chat_id={chat_id})"
            )
            stats.increment_error()

    except Exception as e:
        logger.error(
            f"Ошибка обработки фото от user_id={user_id} (chat_id={chat_id}): {e}",
            exc_info=True,
        )
        stats.increment_error()
        try:
            await message.reply(f"❌ Произошла ошибка: {str(e)}")
        except Exception:
            pass
