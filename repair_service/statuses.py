"""Конвейер статусов заявки.

Единственный источник значений статусов в проекте. Порядок в `PIPELINE` —
часть продукта: его нельзя менять, дополнять или переводить на английский.
"""

from enum import StrEnum


class Status(StrEnum):
    ACCEPTED = "принято"
    DIAGNOSTICS = "диагностика"
    REPAIR = "ремонт"
    READY = "готово"
    HANDED_OVER = "выдано"

    @property
    def position(self) -> int:
        """Порядковый номер в конвейере, начиная с нуля."""
        return PIPELINE.index(self)

    @classmethod
    def from_value(cls, value: str) -> "Status":
        """Восстановить статус из значения, прочитанного из базы."""
        return cls(value)


PIPELINE: tuple[Status, ...] = (
    Status.ACCEPTED,
    Status.DIAGNOSTICS,
    Status.REPAIR,
    Status.READY,
    Status.HANDED_OVER,
)

INITIAL_STATUS: Status = Status.ACCEPTED
