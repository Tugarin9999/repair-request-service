"""Проверки слоя данных по критериям приёмки из `TZ.txt`.

Запуск без сторонних зависимостей: `python tests/test_data.py`
Те же функции подхватываются pytest, если он появится: `pytest tests/`
Каждый тест работает на своей временной БД, основная база не страдает.
"""

import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repair_service import db, repository
from repair_service.models import Request, RequestStatusView
from repair_service.statuses import PIPELINE, Status

COMMENT = "Ждёт деталь"


@contextmanager
def temp_db() -> Iterator[None]:
    """Изолированная БД на время одного теста."""
    previous = os.environ.get(db.config.DATA_DIR_ENV)
    with tempfile.TemporaryDirectory(prefix="rs-test-") as directory:
        os.environ[db.config.DATA_DIR_ENV] = directory
        db.init_db()
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop(db.config.DATA_DIR_ENV, None)
            else:
                os.environ[db.config.DATA_DIR_ENV] = previous


def make_request(device: str = "Ноутбук", fault: str = "Не включается", contact: str = "+7 900 000-00-00") -> Request:
    return repository.create_request(device, fault, contact)


def force_status(number: str, raw: str) -> None:
    """Записать в базу значение статуса в обход проверок слоя доступа."""
    with db.session() as connection:
        connection.execute("UPDATE requests SET status = ? WHERE number = ?", (raw, number))


def test_номера_уникальны_и_в_формате_гггг_0000() -> None:
    with temp_db():
        first = make_request()
        second = make_request()
        assert first.number != second.number, "номера совпали"
        assert first.number.count("-") == 1, first.number
        year, sequence = first.number.split("-")
        assert len(year) == 4 and year.isdigit(), first.number
        assert sequence == "0001", first.number
        assert second.number == f"{year}-0002", second.number


def test_стартовый_статус_первый_в_конвейере() -> None:
    with temp_db():
        assert make_request().status is PIPELINE[0]


def test_клиентская_модель_физически_без_контакта() -> None:
    fields = set(RequestStatusView.__dataclass_fields__)
    assert "contact" not in fields, sorted(fields)
    assert "fault" not in fields, sorted(fields)
    assert fields == {"number", "status", "comment", "updated_at"}, sorted(fields)


def test_клиент_не_видит_контакт() -> None:
    with temp_db():
        request = make_request(contact="+7 900 111-22-33")
        view = repository.get_request_for_client(request.number)
        assert view is not None
        assert not hasattr(view, "contact")
        assert not hasattr(view, "fault")


def test_мастер_видит_контакт() -> None:
    with temp_db():
        request = make_request(contact="+7 900 111-22-33")
        full = repository.get_request_for_master(request.number)
        assert full is not None
        assert full.contact == "+7 900 111-22-33"


def test_клиент_видит_обновление_статуса() -> None:
    with temp_db():
        request = make_request()
        assert repository.update_status(request.number, Status.REPAIR) is True
        view = repository.get_request_for_client(request.number)
        assert view is not None and view.status is Status.REPAIR


def test_смена_статуса_несуществующей_заявки_возвращает_false() -> None:
    with temp_db():
        assert repository.update_status("2026-9999", Status.READY) is False


def test_смена_статуса_не_существует_ничего_не_создаёт() -> None:
    with temp_db():
        make_request()
        repository.update_status("2026-9999", Status.READY)
        numbers = [request.number for request in repository.list_requests()]
        assert len(numbers) == 1, numbers


def test_чтение_несуществующего_номера_возвращает_none() -> None:
    with temp_db():
        assert repository.get_request_for_client("2026-9999") is None
        assert repository.get_request_for_master("2026-9999") is None


def test_не_номер_возвращает_none() -> None:
    with temp_db():
        for value in ("абракадабра", "", "   ", "2026", "2026-", "-0001", "2026-1-1", None):
            assert repository.get_request_for_client(value) is None, value
            assert repository.normalize_number(value) is None, value


def test_комментарий_виден_клиенту() -> None:
    with temp_db():
        request = make_request()
        assert repository.update_comment(request.number, COMMENT) is True
        view = repository.get_request_for_client(request.number)
        assert view is not None and view.comment == COMMENT


def test_комментарий_несуществующей_заявки_возвращает_false() -> None:
    with temp_db():
        assert repository.update_comment("2026-9999", "что-то") is False


def test_список_отсортирован_по_номеру() -> None:
    with temp_db():
        created = [make_request().number for _ in range(3)]
        assert [r.number for r in repository.list_requests()] == sorted(created), created


def test_фильтр_по_статусу() -> None:
    with temp_db():
        first = make_request()
        second = make_request()
        repository.update_status(first.number, Status.REPAIR)
        found = [r.number for r in repository.list_requests(Status.REPAIR)]
        assert found == [first.number], found
        assert second.number not in found


def test_номер_прощает_ввод_как_из_речи() -> None:
    with temp_db():
        request = make_request()
        for variant in ("2026-1", " 2026-0001 ", "2026-1 ", "2026-0001\n", "\u00a02026-0001"):
            assert repository.get_request_for_client(variant) is not None, variant
        assert repository.normalize_number("2026-1") == request.number


def test_пустые_поля_отклоняются() -> None:
    with temp_db():
        for device, fault, contact in (("", "x", "y"), ("x", "  ", "y"), ("x", "y", "")):
            try:
                repository.create_request(device, fault, contact)
            except ValueError:
                continue
            raise AssertionError(f"пустое поле не отклонено: {device!r} {fault!r} {contact!r}")


def test_мусорный_статус_в_базе_даёт_ошибку() -> None:
    with temp_db():
        request = make_request()
        for raw in ("несуществующий", "ACCEPTED", "принято ", "", "0", "0; DROP TABLE requests"):
            force_status(request.number, raw)
            try:
                repository.get_request_for_client(request.number)
            except ValueError:
                continue
            raise AssertionError(f"мусорный статус не вызвал ошибку: {raw!r}")


def test_каждый_статус_конвейера_читается() -> None:
    with temp_db():
        request = make_request()
        for status in PIPELINE:
            force_status(request.number, status.value)
            view = repository.get_request_for_client(request.number)
            assert view is not None and view.status is status, status


def test_статус_вне_конвейера_отклоняется_на_записи() -> None:
    with temp_db():
        request = make_request()
        for bogus in ("принято", "ACCEPTED", "", "готово "):
            try:
                repository.update_status(request.number, bogus)
            except ValueError:
                continue
            raise AssertionError(f"статус вне конвейера принят: {bogus!r}")


def test_повторная_инициализация_схемы_безопасна() -> None:
    with temp_db():
        make_request()
        db.init_db()
        assert len(repository.list_requests()) == 1


def test_даты_создания_и_обновления_корректны() -> None:
    with temp_db():
        request = make_request()
        assert request.created_at <= request.updated_at
        repository.update_status(request.number, Status.REPAIR)
        full = repository.get_request_for_master(request.number)
        assert full.updated_at >= request.updated_at
        view = repository.get_request_for_client(request.number)
        assert view.updated_at == full.updated_at


def _run() -> int:
    tests = [(name, value) for name, value in globals().items() if name.startswith("test_")]
    failed: list[str] = []
    for name, test in tests:
        try:
            test()
        except Exception as error:  # noqa: BLE001
            failed.append(name)
            print(f"FAIL {name}\n     {type(error).__name__}: {error}")
        else:
            print(f"OK   {name}")
    print(f"\n{len(tests) - len(failed)}/{len(tests)} пройдено")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
