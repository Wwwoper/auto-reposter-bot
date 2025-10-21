"""
Модуль для работы с VK API
"""

from .api import VKAPI
from .exceptions import (
    VKAPIError,
    VKUploadError,
    VKEmptyPhotoError,
    VKSavePhotoError,
    VKPostError,
    VKRateLimitError,
    VKGetUploadURLError,
    VKConnectionError,
    VKInvalidTokenError,
)

__all__ = [
    "VKAPI",
    "VKAPIError",
    "VKUploadError",
    "VKEmptyPhotoError",
    "VKSavePhotoError",
    "VKPostError",
    "VKRateLimitError",
    "VKGetUploadURLError",
    "VKConnectionError",
    "VKInvalidTokenError",
]
