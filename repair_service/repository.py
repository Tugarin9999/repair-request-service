"""Доступ к данным.

Чтение по номеру для клиента и для мастера — разные функции с разными
типами результата: клиентская не может отдать контакт, потому что
`RequestStatusView` такого поля не содержит.

Формат номера: `ГГГГ-0000`, сквозной в пределах года. Номер уникален —
это первичный ключ, а не соглашение.
"""

import re
import sqlite3
from datetime import date, datetime

from repair_service.db import session
from repair_service.models import Request, RequestStatusView
from repair_service.statuses import INITIAL_STATUS, PIPELINE, Status

_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
_NUMBER_PATTERN = re.compile(r"^(\d{4})-(\d+)$")
_INSERT_ATTEMPTS = 5

_CLIENT_COLUMNS = "number, status, comment, updated_at"
_MASTER_COLUMNS = "number, device, fault, contact, status, comment, created_at, updated_at"


def create_request(device: str, fault: str, contact: str, comment: str = "") -> Request:
    """Создать заявку с начальным статусом и выдать клиенту её номер."""
    _require_text(device, "Укажите, какое устройство нужно отремонтировать.")
    _require_text(fault, "Опишите, что не работает.")
    _require_text(contact, "Укажите контакт для связи.")

    now = _now()
    for _ in range(_INSERT_ATTEMPTS):
        with session() as connection:
            number = _next_number(connection)
            try:
                connection.execute(
                    "INSERT INTO requests ("
                    " number, device, fault, contact, status, comment, created_at, updated_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        number,
                        device.strip(),
                        fault.strip(),
                        contact.strip(),
                        INITIAL_STATUS.value,
                        comment.strip(),
                        _stamp(now),
                        _stamp(now),
                    ),
                )
            except sqlite3.IntegrityError:
                continue
        return Request(
            number=number,
            device=device.strip(),
            fault=fault.strip(),
            contact=contact.strip(),
            status=INITIAL_STATUS,
            comment=comment.strip(),
            created_at=now,
            updated_at=now,
        )
    raise RuntimeError("Не удалось выдать уникальный номер заявки.")


def get_request_for_client(number: str) -> RequestStatusView | None:
    """Статус и комментарий по номеру для клиента. `None`, если заявки нет.

    Контакт сюда не попадает: функция его не выбирает и не может вернуть.
    """
    normalized = normalize_number(number)
    if normalized is None:
        return None
    with session() as connection:
        row = connection.execute(
            f"SELECT {_CLIENT_COLUMNS} FROM requests WHERE number = ?",
            (normalized,),
        ).fetchone()
    if row is None:
        return None
    return RequestStatusView(
        number=row["number"],
        status=Status.from_value(row["status"]),
        comment=row["comment"],
        updated_at=_parse_time(row["updated_at"]),
    )


def get_request_for_master(number: str) -> Request | None:
    """Полная заявка по номеру для мастера. `None`, если заявки нет."""
    normalized = normalize_number(number)
    if normalized is None:
        return None
    with session() as connection:
        row = connection.execute(
            f"SELECT {_MASTER_COLUMNS} FROM requests WHERE number = ?",
            (normalized,),
        ).fetchone()
    return None if row is None else _to_request(row)


def list_requests(status: Status | None = None) -> list[Request]:
    """Список заявок для мастера, от старых к новым (порядок номера = хронология)."""
    query = f"SELECT {_MASTER_COLUMNS} FROM requests"
    params: tuple[str, ...] = ()
    if status is not None:
        _require_pipeline_status(status)
        query += " WHERE status = ?"
        params = (status.value,)
    query += " ORDER BY number ASC"
    with session() as connection:
        rows = connection.execute(query, params).fetchall()
    return [_to_request(row) for row in rows]


def update_status(number: str, status: Status) -> bool:
    """Сменить статус существующей заявки. `False`, если такой заявки нет.

    Несуществующий номер не вставляет и не меняет ничего: это гарантирует
    сам SQL, а не проверка в коде.
    """
    _require_pipeline_status(status)
    normalized = normalize_number(number)
    if normalized is None:
        return False
    with session() as connection:
        cursor = connection.execute(
            "UPDATE requests SET status = ?, updated_at = ? WHERE number = ?",
            (status.value, _stamp(_now()), normalized),
        )
    return cursor.rowcount > 0


def update_comment(number: str, comment: str) -> bool:
    """Сохранить комментарий мастерской. `False`, если такой заявки нет."""
    normalized = normalize_number(number)
    if normalized is None:
        return False
    with session() as connection:
        cursor = connection.execute(
            "UPDATE requests SET comment = ?, updated_at = ? WHERE number = ?",
            (comment.strip(), _stamp(_now()), normalized),
        )
    return cursor.rowcount > 0


def normalize_number(number: str | None) -> str | None:
    """Привести номер к виду `ГГГГ-0000` или вернуть `None`, если это не номер.

    Клиент диктует номер голосом и вводит `2026-1` вместо `2026-0001`,
    поэтому ведущие нули восстанавливаются, а пробелы и регистр игнорируются.
    """
    if not isinstance(number, str):
        return None
    candidate = number.strip().replace(" ", "").replace("\u00a0", "").upper()
    match = _NUMBER_PATTERN.match(candidate)
    if match is None:
        return None
    year, sequence = match.groups()
    return f"{year}-{int(sequence):04d}"


def _next_number(connection: sqlite3.Connection) -> str:
    prefix = f"{date.today().year}-"
    row = connection.execute(
        "SELECT number FROM requests WHERE number LIKE ? ORDER BY number DESC LIMIT 1",
        (f"{prefix}%",),
    ).fetchone()
    sequence = int(row["number"].rsplit("-", 1)[1]) + 1 if row is not None else 1
    return f"{prefix}{sequence:04d}"


def _to_request(row: sqlite3.Row) -> Request:
    return Request(
        number=row["number"],
        device=row["device"],
        fault=row["fault"],
        contact=row["contact"],
        status=Status.from_value(row["status"]),
        comment=row["comment"],
        created_at=_parse_time(row["created_at"]),
        updated_at=_parse_time(row["updated_at"]),
    )


def _require_text(value: str, message: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(message)


def _require_pipeline_status(status: Status) -> None:
    if not isinstance(status, Status) or status not in PIPELINE:
        raise ValueError(f"Статус {status!r} не входит в конвейер.")


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _stamp(moment: datetime) -> str:
    return moment.strftime(_TIME_FORMAT)


def _parse_time(value: str) -> datetime:
    return datetime.strptime(value, _TIME_FORMAT)
