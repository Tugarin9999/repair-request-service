r"""Проверки экранов через `streamlit.testing.v1.AppTest`.

Нужен установленный streamlit, поэтому этот файл живёт только в `.venv`:

```
.venv\Scripts\python.exe -m pytest tests\test_app.py -q
```

Проверяется главное из критериев приёмки: клиент после подачи заявки видит
номер, статус по номеру обновляется, контакт на клиентском экране не
появляется нигде, а неизвестный номер даёт понятное сообщение.
"""

import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from streamlit.testing.v1 import AppTest

from repair_service import config

APP = REPO_ROOT / "app.py"

ROLE_CLIENT = "Клиент"
ROLE_MASTER = "Мастер"
CONTACT = "+7 900 000-11-22"
COMMENT = "Ждёт деталь с завода"
MASTER_PASSWORD = "мастер-2026"

DEVICE_INPUT, CONTACT_INPUT, NUMBER_INPUT = 0, 1, 2
FAULT_AREA = 0
SEND_BUTTON, LOOKUP_BUTTON = 0, 1


@contextmanager
def temp_db(password: str | None = MASTER_PASSWORD):
    """Изолированная БД на время одного теста."""
    previous_db = os.environ.get(config.DATA_DIR_ENV)
    previous_password = os.environ.get(config.MASTER_PASSWORD_ENV)
    if password is None:
        os.environ.pop(config.MASTER_PASSWORD_ENV, None)
    else:
        os.environ[config.MASTER_PASSWORD_ENV] = password
    with tempfile.TemporaryDirectory(prefix="rs-app-") as directory:
        os.environ[config.DATA_DIR_ENV] = directory
        from repair_service import db

        db.init_db()
        try:
            yield
        finally:
            for key, value in (
                (config.DATA_DIR_ENV, previous_db),
                (config.MASTER_PASSWORD_ENV, previous_password),
            ):
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def open_app() -> AppTest:
    app = AppTest.from_file(str(APP))
    app.run()
    assert not app.exception, app.exception
    return app


def as_master(app: AppTest, password: str = MASTER_PASSWORD) -> AppTest:
    app.radio[0].set_value(ROLE_MASTER).run()
    assert not app.exception, app.exception
    app.text_input[0].set_value(password)
    app.button[0].click().run()
    assert not app.exception, app.exception
    return app


def screen_text(app: AppTest) -> str:
    parts: list[str] = []
    for group in (
        app.markdown,
        app.text,
        app.caption,
        app.info,
        app.warning,
        app.error,
        app.success,
        app.title,
        app.subheader,
    ):
        parts.extend(str(item.value) for item in group)
    return "\n".join(parts)


def submit_request(app: AppTest) -> str:
    app.text_input[DEVICE_INPUT].set_value("Ноутбук")
    app.text_area[FAULT_AREA].set_value("Не включается")
    app.text_input[CONTACT_INPUT].set_value(CONTACT)
    app.button[SEND_BUTTON].click().run()
    assert not app.exception, app.exception
    return issued_number(app)


def issued_number(app: AppTest) -> str:
    for part in screen_text(app).splitlines():
        if "Номер заявки:" in part:
            return part.split("Номер заявки:")[1].strip().strip("*")
    raise AssertionError(f"номер не показан. Экран:\n{screen_text(app)}")


def lookup(app: AppTest, number: str) -> AppTest:
    app.text_input[NUMBER_INPUT].set_value(number)
    app.button[LOOKUP_BUTTON].click().run()
    assert not app.exception, app.exception
    return app


def test_клиент_видит_номер_новой_заявки() -> None:
    with temp_db():
        app = open_app()
        number = submit_request(app)
        assert number == "2026-0001", number
        assert "Заявка принята" in screen_text(app)


def test_клиент_видит_статус_по_номеру() -> None:
    with temp_db():
        app = open_app()
        number = submit_request(app)
        app = lookup(app, number)
        assert "принято" in screen_text(app)


def test_клиент_не_видит_контакт_нигде() -> None:
    with temp_db():
        app = open_app()
        number = submit_request(app)
        app = lookup(app, number)
        assert CONTACT not in screen_text(app)
        assert "контакт" not in screen_text(app).lower().replace("с вами связаться", "")


def test_неизвестный_номер_даёт_понятное_сообщение() -> None:
    with temp_db():
        app = open_app()
        app = lookup(app, "2026-7777")
        text = screen_text(app)
        assert app.warning, "нет предупреждения"
        assert "не нашли" in text.lower() or "нет" in text.lower(), text
        assert "Traceback" not in text


def test_пустая_заявка_не_создаётся() -> None:
    with temp_db():
        app = open_app()
        app.button[SEND_BUTTON].click().run()
        assert not app.exception, app.exception
        assert app.error, "нет сообщения об ошибке"
        assert "2026-0001" not in screen_text(app)


def test_мастер_видит_контакт_в_списке() -> None:
    with temp_db():
        app = open_app()
        number = submit_request(app)
        app = as_master(app)
        assert number in screen_text(app)
        assert CONTACT in app.dataframe[0].value.to_string()


def test_мастер_меняет_статус_клиент_видит_новый() -> None:
    with temp_db():
        app = open_app()
        number = submit_request(app)
        app = as_master(app)
        app.selectbox[-1].set_value("ремонт").run()
        assert not app.exception, app.exception
        app.button[-1].click().run()
        assert not app.exception, app.exception
        assert app.success, "нет подтверждения сохранения"
        client = open_app()
        client = lookup(client, number)
        assert "ремонт" in screen_text(client)


def test_мастер_пишет_комментарий_клиент_его_видит() -> None:
    with temp_db():
        app = open_app()
        number = submit_request(app)
        app = as_master(app)
        app.text_area[-1].set_value(COMMENT)
        app.button[-1].click().run()
        assert not app.exception, app.exception
        client = open_app()
        client = lookup(client, number)
        assert COMMENT in screen_text(client)


def test_без_пароля_экран_мастера_закрыт() -> None:
    with temp_db(password=None):
        app = open_app()
        submit_request(app)
        app.radio[0].set_value(ROLE_MASTER).run()
        assert not app.exception, app.exception
        assert app.error, "нет сообщения о блокировке"
        assert config.MASTER_PASSWORD_ENV in screen_text(app)
        assert not app.dataframe, "список заявок виден без пароля"


def test_неверный_пароль_не_пускает_к_списку() -> None:
    with temp_db():
        app = open_app()
        submit_request(app)
        app = as_master(app, "неправильный")
        assert app.error, "нет отказа"
        assert not app.dataframe, "список заявок виден с неверным паролем"


def test_верный_пароль_открывает_список() -> None:
    with temp_db():
        app = open_app()
        submit_request(app)
        app = as_master(app)
        assert not app.error, "вход не выполнен"
        assert app.dataframe, "список заявок не показан"


def test_выход_снова_закрывает_экран() -> None:
    with temp_db():
        app = open_app()
        submit_request(app)
        app = as_master(app)
        assert app.dataframe
        app.button[0].click().run()
        assert not app.exception, app.exception
        assert not app.dataframe, "после выхода список всё ещё виден"
        assert app.text_input[0].label == "Пароль"


def test_клиентский_экран_пароля_не_требует() -> None:
    with temp_db():
        app = open_app()
        number = submit_request(app)
        app = lookup(app, number)
        assert "принято" in screen_text(app)
