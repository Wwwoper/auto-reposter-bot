import asyncio
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.utils.logger import logger
from src.utils.file_validator import FileValidator
from src.config.constants import (
    VK_API_TIMEOUT,
    VK_RETRY_STATUS_CODES,
)
from src.vk.exceptions import (
    VKSavePhotoError,
    VKPostError,
    VKGetUploadURLError,
)


@dataclass
class VKAPI:
    ACCESS_TOKEN: str
    GROUP_TOKEN: str
    GROUP_ID: str
    V: str

    session: Session = field(default_factory=Session)
    max_retries: int = 3
    _request_times: deque = field(default_factory=lambda: deque(maxlen=3))

    def __post_init__(self):
        """Настройка сессии с retry механизмом"""
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=VK_RETRY_STATUS_CODES,
            allowed_methods=["POST", "GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    async def _rate_limit(self):
        """Простой rate limiter: не более 3 запросов в секунду"""
        if len(self._request_times) == 3:
            oldest = self._request_times[0]
            elapsed = (datetime.now() - oldest).total_seconds()
            if elapsed < 1.0:
                delay = 1.1 - elapsed
                logger.debug(f"Rate limit: пауза {delay:.2f}s")
                await asyncio.sleep(delay)

        self._request_times.append(datetime.now())

    async def create_post_from_wall(
        self, file_path: str, message: str
    ) -> Optional[Dict]:
        """
        Создает пост на стене ВК с изображением

        Args:
            file_path: путь к файлу изображения
            message: текст поста

        Returns:
            Результат публикации или None в случае ошибки
        """
        await self._rate_limit()  # Контроль частоты запросов
        try:
            # Быстрая проверка валидности (основная проверка уже выполнена)
            validator = FileValidator()
            if not await validator.validate_image_file(file_path):
                logger.error(f"Файл {file_path} не прошел валидацию")
                return None

            upload_url = self._get_upload_url()
            server, photo, hash_value = self._upload_image(upload_url, file_path)

            # Проверка, что photo не пустой
            if not photo:
                logger.error(f"Получен пустой ответ photo от ВК для файла {file_path}")
                return None

            photo_attachment = self._post_save_wall_photo(server, photo, hash_value)
            result = self._wall_post(photo_attachment, message)

            logger.info(f"Пост успешно опубликован: {result}")

            # Удаление файла после успешной публикации
            await self._cleanup_file(file_path)

            return result

        except KeyError as e:
            logger.error(f"Ошибка создания поста на стены (отсутствует ключ): {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при создании поста: {e}", exc_info=True)
            return None

    async def verify_file_ready(self, file_path: str, max_attempts: int = 3) -> bool:
        """
        Проверяет, что файл полностью записан и готов к чтению

        Args:
            file_path: путь к файлу
            max_attempts: максимальное количество попыток

        Returns:
            True если файл готов, False иначе
        """
        for attempt in range(max_attempts):
            try:
                # Пытаемся открыть файл для чтения
                with open(file_path, "rb") as f:
                    # Читаем первые байты для проверки доступности
                    f.read(1024)
                logger.debug(
                    f"Файл {file_path} готов к загрузке (попытка {attempt + 1})"
                )
                return True
            except (IOError, OSError) as e:
                logger.warning(
                    f"Файл {file_path} еще не готов (попытка {attempt + 1}): {e}"
                )
                if attempt < max_attempts - 1:
                    await asyncio.sleep(
                        0.3 * (attempt + 1)
                    )  # Экспоненциальная задержка

        logger.error(f"Не удалось дождаться готовности файла {file_path}")
        return False

    async def _validate_image(self, file_path: str) -> bool:
        """
        Валидация изображения перед загрузкой

        Args:
            file_path: путь к файлу

        Returns:
            True если файл валиден, False иначе
        """
        path = Path(file_path)

        # Проверка существования
        if not path.exists():
            logger.error(f"Файл {file_path} не существует")
            return False

        # Проверка размера (ВК имеет лимит ~50MB)
        file_size = path.stat().st_size
        max_size = 50 * 1024 * 1024  # 50 MB
        if file_size == 0:
            logger.error(f"Файл {file_path} пустой (0 байт)")
            return False
        if file_size > max_size:
            logger.error(f"Файл {file_path} слишком большой: {file_size} байт")
            return False

        # Проверка расширения
        allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}
        if path.suffix.lower() not in allowed_extensions:
            logger.error(f"Неподдерживаемый формат файла: {path.suffix}")
            return False

        logger.debug(f"Файл {file_path} прошел валидацию (размер: {file_size} байт)")
        return True

    def _get_upload_url(self) -> str:
        """Получение URL для загрузки изображения"""
        try:
            upload_server_response: Dict = self.session.post(
                url="https://api.vk.com/method/photos.getWallUploadServer",
                params={
                    "access_token": self.ACCESS_TOKEN,
                    "group_id": self.GROUP_ID,
                    "v": self.V,
                },
                timeout=VK_API_TIMEOUT,
            ).json()

            logger.debug(f"get_upload_url response: {upload_server_response}")

            if "error" in upload_server_response:
                error_msg = upload_server_response["error"].get(
                    "error_msg", "Unknown error"
                )
                logger.error(f"Ошибка API ВК при получении upload URL: {error_msg}")
                raise VKGetUploadURLError(
                    error_msg, error_code=error_code, error_msg=error_msg
                )

            return upload_server_response["response"]["upload_url"]

        except KeyError as e:
            logger.error(f"Ошибка получения URL для загрузки: {e}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении upload URL: {e}")
            raise

    def _upload_image(
        self, upload_url: str, file_path: str, max_retries: int = 3
    ) -> tuple:
        """
        Загружает изображение на сервер ВК

        Args:
            upload_url: URL для загрузки
            file_path: Путь к файлу изображения
            max_retries: Максимальное количество попыток

        Returns:
            tuple: (server, photo, hash) параметры загруженного изображения

        Raises:
            ValueError: Если получен пустой параметр photo после всех попыток
            Exception: При других ошибках загрузки
        """
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                with open(file_path, "rb") as photo_file:
                    files = {"photo": photo_file}
                    response = requests.post(upload_url, files=files, timeout=30)
                    response.raise_for_status()

                    result = response.json()
                    logger.debug(f"upload_image response (попытка {attempt}): {result}")

                    # Проверка наличия обязательных полей
                    if "photo" not in result or not result["photo"]:
                        # ВАЖНО: Это WARNING, не ERROR - мы еще будем повторять попытку
                        logger.warning(
                            f"Получен пустой параметр 'photo' (попытка {attempt}/{max_retries}). "
                            f"Возможно файл еще не полностью записан на диск."
                        )

                        if attempt < max_retries:
                            # Экспоненциальная задержка между попытками
                            wait_time = 2 ** (attempt - 1)
                            logger.info(
                                f"Повторная попытка через {wait_time} секунд..."
                            )
                            time.sleep(wait_time)
                            last_error = ValueError(
                                "Empty photo parameter received after all retries"
                            )
                            continue
                        else:
                            # Только на последней попытке это ERROR
                            raise ValueError(
                                "Empty photo parameter received after all retries"
                            )

                    # Успешная загрузка
                    server = result.get("server")
                    photo = result.get("photo")
                    hash_value = result.get("hash")

                    # Логируем успех только если была не первая попытка
                    if attempt > 1:
                        logger.info(
                            f"✅ Загрузка успешна с попытки {attempt}/{max_retries}"
                        )

                    return server, photo, hash_value

            except requests.RequestException as e:
                # ВАЖНО: Это WARNING, не ERROR - мы еще будем повторять попытку
                logger.warning(
                    f"Ошибка сети при загрузке изображения (попытка {attempt}/{max_retries}): {e}"
                )
                last_error = e

                if attempt < max_retries:
                    wait_time = 2 ** (attempt - 1)
                    logger.info(f"Повторная попытка через {wait_time} секунд...")
                    time.sleep(wait_time)
                else:
                    # Только на последней попытке это ERROR
                    logger.error(
                        f"Не удалось загрузить изображение после {max_retries} попыток"
                    )
                    raise

            except Exception as e:
                # Непредвиденная ошибка - это сразу ERROR, но только на последней попытке
                if attempt >= max_retries:
                    logger.error(
                        f"Неожиданная ошибка при загрузке изображения (попытка {attempt}): {e}"
                    )
                else:
                    logger.warning(
                        f"Неожиданная ошибка при загрузке изображения (попытка {attempt}): {e}"
                    )
                last_error = e

                if attempt < max_retries:
                    wait_time = 2 ** (attempt - 1)
                    logger.info(f"Повторная попытка через {wait_time} секунд...")
                    time.sleep(wait_time)
                else:
                    raise

        # Если дошли сюда, значит все попытки исчерпаны
        logger.error(f"Не удалось загрузить изображение после {max_retries} попыток")
        raise (
            last_error if last_error else ValueError("Upload failed after all retries")
        )

    def _post_save_wall_photo(self, server: int, photo: str, hash_value: str) -> str:
        """Сохранение загруженного изображения"""
        try:
            save_response = self.session.post(
                url="https://api.vk.com/method/photos.saveWallPhoto",
                params={
                    "access_token": self.ACCESS_TOKEN,
                    "group_id": self.GROUP_ID,
                    "server": server,
                    "photo": photo,
                    "hash": hash_value,
                    "v": self.V,
                },
                timeout=VK_API_TIMEOUT,
            ).json()

            logger.debug(f"post_save_wall_photo response: {save_response}")

            if "error" in save_response:
                error_msg = save_response["error"].get("error_msg", "Unknown error")
                logger.error(f"Ошибка API ВК при сохранении фото: {error_msg}")
                raise VKSavePhotoError(
                    error_msg, error_code=error_code, error_msg=error_msg
                )

            photo_data = save_response["response"][0]
            photo_attachment = f"photo{photo_data['owner_id']}_{photo_data['id']}"

            return photo_attachment

        except KeyError as e:
            logger.error(f"Ошибка сохранения изображения (отсутствует ключ): {e}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при сохранении изображения: {e}")
            raise

    def _wall_post(self, photo_attachment: str, message: str) -> Dict:
        """Публикация поста на стене"""
        try:
            post_response = self.session.post(
                url="https://api.vk.com/method/wall.post",
                params={
                    "access_token": self.GROUP_TOKEN,
                    "v": self.V,
                },
                data={
                    "owner_id": -int(self.GROUP_ID),
                    "message": message,
                    "attachments": photo_attachment,
                },
                timeout=VK_API_TIMEOUT,
            ).json()

            logger.debug(f"Публикация поста на стене: {post_response}")

            if "error" in post_response:
                error_msg = post_response["error"].get("error_msg", "Unknown error")
                logger.error(f"Ошибка API ВК при публикации поста: {error_msg}")
                raise VKPostError(error_msg, error_code=error_code, error_msg=error_msg)

            return post_response

        except KeyError as e:
            logger.error(f"Ошибка публикации поста на стене (отсутствует ключ): {e}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при публикации поста: {e}")
            raise

    async def _cleanup_file(self, file_path: str) -> None:
        """Удаление временного файла"""
        try:
            await asyncio.to_thread(os.remove, file_path)
            logger.debug(f"Файл {file_path} успешно удален после публикации")
        except FileNotFoundError:
            logger.warning(f"Файл {file_path} уже удален")
        except Exception as e:
            logger.error(f"Ошибка при удалении файла {file_path}: {e}")
