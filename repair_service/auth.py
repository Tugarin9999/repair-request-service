"""Пароль экрана мастера.

Пароль живёт только в переменной окружения `REPAIR_SERVICE_MASTER_PASSWORD`
и нигде не сохраняется — ни в репозитории, ни на диске. Сравнение —
постоянного времени, чтобы нельзя было подбирать пароль замером времени
ответа. Сравниваются байты UTF-8: `hmac.compare_digest` отказывается
работать с не-ASCII строками, а пароль здесь почти наверняка кириллический.

Чего это не делает: Streamlit не имеет серверного слоя сессий, поэтому пароль
— шлюз в интерфейсе, а не настоящая аутентификация. Он не защищает файл базы
и не защищает трафик: по обычному HTTP пароль уходит открытым текстом.
"""

import hmac
import os

from repair_service.config import MASTER_PASSWORD_ENV

MIN_LENGTH = 6


def configured() -> bool:
    """Задан ли пароль вообще. Без него экран мастера остаётся закрытым."""
    return bool(expected())


def is_weak() -> bool:
    """Слишком короткий пароль — предупреждаем, но не блокируем."""
    return 0 < len(expected()) < MIN_LENGTH


def verify(candidate: str) -> bool:
    """Проверить введённый пароль."""
    secret = expected()
    if not secret or not isinstance(candidate, str):
        return False
    return hmac.compare_digest(candidate.encode("utf-8"), secret.encode("utf-8"))


def expected() -> str:
    return os.environ.get(MASTER_PASSWORD_ENV, "")