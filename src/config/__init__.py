
"""
Конфигурация приложения
"""
from .settings import Settings, get_settings, settings
from . import constants

__all__ = ['Settings', 'get_settings', 'settings', 'constants']
