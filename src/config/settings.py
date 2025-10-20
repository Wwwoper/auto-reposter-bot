"""
Конфигурация приложения из переменных окружения
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Set, Optional

from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()


@dataclass
class Settings:
    """Настройки приложения"""
    
    # Telegram Bot
    telegram_token: str
    white_list: Set[int]
    
    # VK API
    vk_access_token: str
    vk_group_token: str
    vk_group_id: str
    vk_api_version: str = "5.199"
    
    # Пути к данным
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)
    logs_dir: Path = field(init=False)
    temp_photos_dir: Path = field(init=False)
    
    # Лимиты и ограничения
    max_file_size_mb: int = 50
    rate_limit_per_second: int = 3
    max_retries: int = 3
    
    # Очистка и обслуживание
    cleanup_age_hours: int = 1
    cleanup_interval_hours: int = 1
    
    # Статистика
    stats_report_interval: int = 10  # Каждые 10 успешных постов
    
    # Логирование
    log_level: str = "INFO"
    log_max_bytes: int = 10 * 1024 * 1024  # 10 MB
    log_backup_count: int = 3
    
    def __post_init__(self):
        """Инициализация вычисляемых полей"""
        self.logs_dir = self.base_dir / "data" / "logs"
        self.temp_photos_dir = self.base_dir / "data" / "temp_photos"
        
        # Создание директорий если не существуют
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.temp_photos_dir.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def from_env(cls) -> "Settings":
        """
        Создание настроек из переменных окружения
        
        Raises:
            ValueError: Если отсутствуют обязательные переменные
        """
        # Проверка обязательных переменных
        required_vars = [
            'API_TOKEN',
            'WHITE_LIST',
            'ACCESS_TOKEN',
            'GROUP_TOKEN',
            'GROUP_ID',
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(
                f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}"
            )
        
        # Парсинг WHITE_LIST
        try:
            white_list_str = os.getenv('WHITE_LIST', '')
            white_list = {
                int(x.strip()) 
                for x in white_list_str.split(',') 
                if x.strip()
            }
        except ValueError as e:
            raise ValueError(f"Ошибка парсинга WHITE_LIST: {e}")
        
        return cls(
            telegram_token=os.getenv('API_TOKEN'),
            white_list=white_list,
            vk_access_token=os.getenv('ACCESS_TOKEN'),
            vk_group_token=os.getenv('GROUP_TOKEN'),
            vk_group_id=os.getenv('GROUP_ID'),
            vk_api_version=os.getenv('V', '5.199'),
            # Опциональные параметры
            max_file_size_mb=int(os.getenv('MAX_FILE_SIZE_MB', '50')),
            rate_limit_per_second=int(os.getenv('RATE_LIMIT_PER_SECOND', '3')),
            max_retries=int(os.getenv('MAX_RETRIES', '3')),
            cleanup_age_hours=int(os.getenv('CLEANUP_AGE_HOURS', '1')),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
        )
    
    @property
    def max_file_size_bytes(self) -> int:
        """Максимальный размер файла в байтах"""
        return self.max_file_size_mb * 1024 * 1024
    
    def validate(self) -> None:
        """
        Валидация настроек
        
        Raises:
            ValueError: Если настройки некорректны
        """
        if not self.telegram_token:
            raise ValueError("Telegram token не может быть пустым")
        
        if not self.white_list:
            raise ValueError("WHITE_LIST не может быть пустым")
        
        if not self.vk_access_token or not self.vk_group_token:
            raise ValueError("VK токены не могут быть пустыми")
        
        if self.max_file_size_mb <= 0:
            raise ValueError("MAX_FILE_SIZE_MB должен быть положительным")
        
        if self.rate_limit_per_second <= 0:
            raise ValueError("RATE_LIMIT_PER_SECOND должен быть положительным")
    
    def __repr__(self) -> str:
        """Безопасное представление (без токенов)"""
        return (
            f"Settings("
            f"telegram_token='***', "
            f"white_list={self.white_list}, "
            f"vk_group_id={self.vk_group_id}, "
            f"vk_api_version={self.vk_api_version}"
            f")"
        )


# Глобальный экземпляр настроек (ленивая инициализация)
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Получить глобальный экземпляр настроек (singleton)
    
    Returns:
        Settings: Настройки приложения
    """
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
        _settings.validate()
    return _settings


def reset_settings() -> None:
    """Сбросить глобальный экземпляр настроек (для тестов)"""
    global _settings
    _settings = None


# Для удобства импорта
settings = get_settings