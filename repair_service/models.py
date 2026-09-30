"""Модель заявки и модель для клиентского экрана.

`Request` — полная заявка, доступна только мастерскому экрану.

`RequestStatusView` — то, что видит клиент по номеру: статус и комментарий,
ровно как обещает `TZ.txt`. Поля `contact` и `fault` в ней нет физически,
поэтому контакт не может утечь в клиентский экран даже по ошибке.
"""

from dataclasses import dataclass
from datetime import datetime

from repair_service.statuses import Status


@dataclass(frozen=True, slots=True)
class Request:
    """Заявка целиком. Только для мастерского экрана."""

    number: str
    device: str
    fault: str
    contact: str
    status: Status
    comment: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class RequestStatusView:
    """Ответ на запрос клиента: номер, статус, комментарий, дата обновления."""

    number: str
    status: Status
    comment: str
    updated_at: datetime
