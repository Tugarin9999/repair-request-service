"""Проверки пароля экрана мастера.

Запускаются без зависимостей: `python tests\\test_auth.py`
"""

import os
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repair_service import auth
from repair_service.config import MASTER_PASSWORD_ENV

PASSWORD = "мастер-2026"


@contextmanager
def password(value: str | None):
    previous = os.environ.get(MASTER_PASSWORD_ENV)
    if value is None:
        os.environ.pop(MASTER_PASSWORD_ENV, None)
    else:
        os.environ[MASTER_PASSWORD_ENV] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(MASTER_PASSWORD_ENV, None)
        else:
            os.environ[MASTER_PASSWORD_ENV] = previous


def test_без_пароля_экран_закрыт() -> None:
    with password(None):
        assert auth.configured() is False
        assert auth.verify(PASSWORD) is False
        assert auth.verify("") is False


def test_пустой_пароль_считается_незаданным() -> None:
    with password(""):
        assert auth.configured() is False


def test_верный_пароль_проходит() -> None:
    with password(PASSWORD):
        assert auth.configured() is True
        assert auth.verify(PASSWORD) is True


def test_неверный_пароль_не_проходит() -> None:
    with password(PASSWORD):
        for wrong in ("", " ", PASSWORD + " ", PASSWORD.upper(), PASSWORD[:-1], "мастер-2025"):
            assert auth.verify(wrong) is False, wrong


def test_сравнение_устойчиво_к_не_строке() -> None:
    with password(PASSWORD):
        for candidate in (None, 42, [], object()):
            assert auth.verify(candidate) is False


def test_короткий_пароль_помечен_как_слабый() -> None:
    with password("1234"):
        assert auth.configured() is True
        assert auth.is_weak() is True
        assert auth.verify("1234") is True
    with password(PASSWORD):
        assert auth.is_weak() is False


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