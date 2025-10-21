"""
Кастомные исключения для работы с VK API
"""


class VKAPIError(Exception):
    """Базовое исключение для всех ошибок VK API"""
    
    def __init__(self, message: str, error_code: int = None, error_msg: str = None):
        self.message = message
        self.error_code = error_code
        self.error_msg = error_msg
        super().__init__(self.message)
    
    def __str__(self):
        if self.error_code and self.error_msg:
            return f"{self.message} (код: {self.error_code}, сообщение: {self.error_msg})"
        return self.message


class VKUploadError(VKAPIError):
    """Ошибка при загрузке файла на сервер VK"""
    
    def __init__(self, message: str = "Ошибка загрузки файла на сервер VK", **kwargs):
        super().__init__(message, **kwargs)


class VKEmptyPhotoError(VKUploadError):
    """Получен пустой параметр photo от VK (файл не загрузился)"""
    
    def __init__(self, message: str = "Получен пустой параметр 'photo' от VK", **kwargs):
        super().__init__(message, **kwargs)


class VKSavePhotoError(VKAPIError):
    """Ошибка при сохранении фотографии через API"""
    
    def __init__(self, message: str = "Ошибка сохранения фотографии", **kwargs):
        super().__init__(message, **kwargs)


class VKPostError(VKAPIError):
    """Ошибка при публикации поста на стене"""
    
    def __init__(self, message: str = "Ошибка публикации поста на стене", **kwargs):
        super().__init__(message, **kwargs)


class VKRateLimitError(VKAPIError):
    """Превышен лимит запросов к VK API"""
    
    def __init__(self, message: str = "Превышен лимит запросов к VK API", **kwargs):
        super().__init__(message, **kwargs)


class VKGetUploadURLError(VKAPIError):
    """Ошибка при получении URL для загрузки"""
    
    def __init__(self, message: str = "Ошибка получения URL для загрузки", **kwargs):
        super().__init__(message, **kwargs)


class VKConnectionError(VKAPIError):
    """Ошибка соединения с VK API"""
    
    def __init__(self, message: str = "Ошибка соединения с VK API", **kwargs):
        super().__init__(message, **kwargs)


class VKInvalidTokenError(VKAPIError):
    """Недействительный токен доступа"""
    
    def __init__(self, message: str = "Недействительный токен доступа VK", **kwargs):
        super().__init__(message, **kwargs)