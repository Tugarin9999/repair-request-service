"""Подключение к SQLite и схема таблицы заявок.

Схема применяется идемпотентно при старте, миграций нет: набор статусов
задан требованиями и не меняется, поэтому он не дублируется в CONSTRAINT,
а проверяется в слое доступа к данным.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from repair_service import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    number     TEXT PRIMARY KEY,
    device     TEXT NOT NULL,
    fault      TEXT NOT NULL,
    contact    TEXT NOT NULL,
    status     TEXT NOT NULL,
    comment    TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Открыть соединение, при необходимости создав каталог данных.

    Путь по умолчанию вычисляется в момент вызова, а не на импорте, поэтому
    подмена `REPAIR_SERVICE_DATA_DIR` действует сразу.
    """
    target = path or config.db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def session(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Соединение в транзакции: коммит при успехе, откат при ошибке, всегда закрытие."""
    connection = connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db(path: Path | None = None) -> None:
    """Применить схему. Повторный вызов безопасен."""
    with session(path) as connection:
        connection.executescript(SCHEMA)
