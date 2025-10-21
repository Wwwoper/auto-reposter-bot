"""
Модуль для сбора и анализа статистики работы бота
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
import pytz


class Statistics:
    """Класс для сбора и предоставления статистики работы бота"""

    def __init__(self):
        # Общая статистика за все время
        self.total_success: int = 0
        self.total_errors: int = 0
        self.start_time: datetime = datetime.now(pytz.UTC)

        # Статистика за текущие сутки (МСК)
        self.daily_success: int = 0
        self.daily_errors: int = 0
        self.daily_reset_date: Optional[datetime] = None

        # Настройки
        self.report_interval: int = 10  # Логировать статистику каждые N постов
        self.moscow_tz = pytz.timezone("Europe/Moscow")

        # Инициализация даты сброса
        self._check_and_reset_daily()

    def _check_and_reset_daily(self) -> None:
        """
        Проверяет и сбрасывает дневную статистику если наступил новый день по МСК
        """
        now_msk = datetime.now(self.moscow_tz)
        today_msk = now_msk.replace(hour=0, minute=0, second=0, microsecond=0)

        # Если это первый запуск или наступил новый день
        if self.daily_reset_date is None or self.daily_reset_date < today_msk:
            self.daily_success = 0
            self.daily_errors = 0
            self.daily_reset_date = today_msk

    def increment_success(self) -> None:
        """Увеличивает счетчик успешных публикаций"""
        self._check_and_reset_daily()
        self.total_success += 1
        self.daily_success += 1

    def increment_error(self) -> None:
        """Увеличивает счетчик ошибок (только финальных, не повторных попыток)"""
        self._check_and_reset_daily()
        self.total_errors += 1
        self.daily_errors += 1

    def should_log_stats(self) -> bool:
        """
        Проверяет, нужно ли логировать статистику

        Returns:
            bool: True если пора логировать (каждые N постов)
        """
        total_posts = self.total_success + self.total_errors
        return total_posts > 0 and total_posts % self.report_interval == 0

    def get_uptime(self) -> timedelta:
        """
        Возвращает время работы бота

        Returns:
            timedelta: Время с момента запуска
        """
        return datetime.now(pytz.UTC) - self.start_time

    def get_success_rate(self, use_daily: bool = False) -> float:
        """
        Вычисляет процент успешных публикаций

        Args:
            use_daily: Если True, возвращает статистику за сутки

        Returns:
            float: Процент успешных публикаций (0-100)
        """
        if use_daily:
            total = self.daily_success + self.daily_errors
            success = self.daily_success
        else:
            total = self.total_success + self.total_errors
            success = self.total_success

        if total == 0:
            return 0.0
        return (success / total) * 100

    def get_total_posts(self, use_daily: bool = False) -> int:
        """
        Возвращает общее количество обработанных постов

        Args:
            use_daily: Если True, возвращает статистику за сутки

        Returns:
            int: Общее количество постов
        """
        if use_daily:
            return self.daily_success + self.daily_errors
        return self.total_success + self.total_errors

    def format_uptime(self) -> str:
        """
        Форматирует время работы в читаемый вид

        Returns:
            str: Отформатированное время (например, "5д 12ч 30м")
        """
        uptime = self.get_uptime()
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days}д")
        if hours > 0 or days > 0:
            parts.append(f"{hours}ч")
        parts.append(f"{minutes}м")

        return " ".join(parts)

    def get_report(self, include_daily: bool = True) -> str:
        """
        Генерирует текстовый отчет статистики

        Args:
            include_daily: Включать ли статистику за сутки

        Returns:
            str: Отформатированный отчет
        """
        self._check_and_reset_daily()

        uptime = self.format_uptime()
        total_posts = self.get_total_posts()
        success_rate = self.get_success_rate()

        report_lines = [
            "📊 Статистика бота",
            "",
            f"⏱ Время работы: {uptime}",
        ]

        if include_daily and (self.daily_success > 0 or self.daily_errors > 0):
            daily_rate = self.get_success_rate(use_daily=True)
            daily_total = self.get_total_posts(use_daily=True)

            report_lines.extend(
                [
                    "",
                    "📅 За текущие сутки (МСК):",
                    f"✅ Успешных постов: {self.daily_success}",
                    f"❌ Ошибок: {self.daily_errors}",
                    f"📈 Success rate: {daily_rate:.1f}%",
                    f"📝 Всего получено для отправки: {daily_total}",
                ]
            )

        report_lines.extend(
            [
                "",
                "📊 За все время:",
                f"✅ Успешных постов: {self.total_success}",
                f"❌ Ошибок: {self.total_errors}",
                f"📈 Success rate: {success_rate:.1f}%",
                f"📝 Всего обработано: {total_posts}",
            ]
        )

        return "\n".join(report_lines)

    def get_log_stats(self) -> str:
        """
        Генерирует краткую статистику для логов

        Returns:
            str: Краткая статистика для вывода в лог
        """
        self._check_and_reset_daily()

        uptime = self.format_uptime()
        success_rate = self.get_success_rate()

        return (
            f"📊 Статистика: "
            f"✅{self.total_success} ❌{self.total_errors} "
            f"({success_rate:.1f}%) за {uptime}"
        )

    def get_current_msk_time(self) -> datetime:
        """
        Возвращает текущее время в часовом поясе МСК

        Returns:
            datetime: Текущее время МСК
        """
        return datetime.now(self.moscow_tz)

    def reset_daily_stats(self) -> None:
        """Принудительно сбрасывает дневную статистику"""
        self.daily_success = 0
        self.daily_errors = 0
        self.daily_reset_date = datetime.now(self.moscow_tz).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    def get_dict(self) -> Dict:
        """
        Возвращает статистику в виде словаря

        Returns:
            Dict: Словарь со всей статистикой
        """
        self._check_and_reset_daily()

        return {
            "total": {
                "success": self.total_success,
                "errors": self.total_errors,
                "total": self.get_total_posts(),
                "success_rate": self.get_success_rate(),
            },
            "daily": {
                "success": self.daily_success,
                "errors": self.daily_errors,
                "total": self.get_total_posts(use_daily=True),
                "success_rate": self.get_success_rate(use_daily=True),
                "reset_date": self.daily_reset_date.isoformat()
                if self.daily_reset_date
                else None,
            },
            "uptime": {
                "formatted": self.format_uptime(),
                "seconds": int(self.get_uptime().total_seconds()),
            },
        }


# Глобальный экземпляр статистики
_stats = Statistics()


def get_stats() -> Statistics:
    """
    Возвращает глобальный экземпляр статистики

    Returns:
        Statistics: Объект статистики
    """
    return _stats


def reset_daily_stats() -> None:
    """
    Принудительно сбрасывает дневную статистику (через глобальный экземпляр)
    """
    _stats.reset_daily_stats()
