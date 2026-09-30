"""Экран мастера: список заявок и смена статусов.

Единственное место, где видны контакты. За закрытым паролем, потому что
контакты клиентов не должны достаться тому, кто просто открыл приложение.

Статус выбирается только из `PIPELINE`, и сохранить его можно только для
заявки, которая реально существует: `repository.update_status` вернёт `False`,
если номера нет.
"""

import streamlit as st

from repair_service import auth, repository
from repair_service.config import MASTER_PASSWORD_ENV
from repair_service.models import Request
from repair_service.statuses import PIPELINE, Status

FILTER_ALL = "все заявки"
UNLOCKED = "master_unlocked"


def render() -> None:
    if not auth.configured():
        st.error(
            f"Экран мастера закрыт: не задана переменная окружения "
            f"{MASTER_PASSWORD_ENV}. Запусти приложение с паролем мастерской."
        )
        return
    if not st.session_state.get(UNLOCKED):
        _render_login()
        return
    _render_queue()


def _render_login() -> None:
    st.subheader("Вход для мастера")
    if auth.is_weak():
        st.warning(
            f"Пароль короче {auth.MIN_LENGTH} символов — мастерскую лучше защитить "
            "длиннее."
        )
    with st.form("master_login", clear_on_submit=False):
        typed = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Войти")

    if not submitted:
        return
    if auth.verify(typed):
        st.session_state[UNLOCKED] = True
        st.rerun()
    st.error("Пароль не подходит.")


def _render_queue() -> None:
    st.subheader("Заявки")
    st.button("Выйти", on_click=_logout)
    labels = [FILTER_ALL, *(status.value for status in PIPELINE)]
    chosen = st.selectbox("Показать", labels, label_visibility="collapsed")
    requests = repository.list_requests() if chosen == FILTER_ALL else repository.list_requests(Status(chosen))

    if not requests:
        st.info("Заявок пока нет.")
        return

    st.dataframe(_as_table(requests), hide_index=True)
    st.divider()
    _render_editor(requests)


def _as_table(requests: list[Request]) -> dict[str, list[object]]:
    return {
        "Номер": [request.number for request in requests],
        "Устройство": [request.device for request in requests],
        "Неисправность": [request.fault for request in requests],
        "Контакт": [request.contact for request in requests],
        "Статус": [request.status.value for request in requests],
        "Создана": [f"{request.created_at:%d.%m.%Y %H:%M}" for request in requests],
    }


def _render_editor(requests: list[Request]) -> None:
    numbers = [request.number for request in requests]
    number = st.selectbox("Заявка для работы", numbers)
    request = repository.get_request_for_master(number)
    if request is None:
        st.error("Заявка не найдена. Обновите список.")
        return

    with st.container(border=True):
        st.markdown(f"### {request.number}")
        st.write(f"**Устройство:** {request.device}")
        st.write(f"**Неисправность:** {request.fault}")
        st.write(f"**Контакт:** {request.contact}")
        st.write(f"**Создана:** {request.created_at:%d.%m.%Y %H:%M}")

        with st.form(f"edit_{request.number}", clear_on_submit=False):
            chosen = st.selectbox(
                "Статус",
                PIPELINE,
                index=request.status.position,
                format_func=lambda status: status.value,
            )
            comment = st.text_area("Комментарий для клиента", value=request.comment, height=80)
            saved = st.form_submit_button("Сохранить")

        if saved:
            _save(request.number, Status(chosen), comment)


def _save(number: str, status: Status, comment: str) -> None:
    if not repository.update_status(number, status):
        st.error("Не удалось сохранить: такой заявки нет. Обновите список.")
        return
    repository.update_comment(number, comment)
    st.success(f"Сохранено. Клиент увидит статус «{status.value}» по номеру {number}.")


def _logout() -> None:
    st.session_state[UNLOCKED] = False
