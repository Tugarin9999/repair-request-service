"""Пути и настройки приложения."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR_ENV = "REPAIR_SERVICE_DATA_DIR"
MASTER_PASSWORD_ENV = "REPAIR_SERVICE_MASTER_PASSWORD"
DB_FILENAME = "requests.db"

PAGE_TITLE = "Ремонтная мастерская"
PAGE_ICON = "🔧"

ROLE_CLIENT = "Клиент"
ROLE_MASTER = "Мастер"


def data_dir() -> Path:
    """Каталог данных. Переопределяется переменной окружения — нужно для тестов."""
    return Path(os.environ.get(DATA_DIR_ENV, BASE_DIR / "data"))


def db_path() -> Path:
    return data_dir() / DB_FILENAME
