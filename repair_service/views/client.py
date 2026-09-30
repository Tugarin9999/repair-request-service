"""Экран клиента: подача заявки и проверка статуса по номеру.

Контакты клиента сюда не выводятся ни при каких условиях. Статус приходит
из `repository.get_request_for_client`, который отдаёт `RequestStatusView` —
в ней физически нет полей `contact` и `fault`.
"""

import streamlit as st

from repair_service import repository
from repair_service.models import RequestStatusView
from repair_service.statuses import PIPELINE

ISSUED_NUMBER = "client_issued_number"


def render() -> None:
    st.subheader("Оставить заявку")
    _render_form()
    st.divider()
    st.subheader("Проверить статус")
    _render_lookup()


def _render_form() -> None:
    with st.form("new_request", clear_on_submit=True):
        device = st.text_input("Какое устройство?", placeholder="Например, ноутбук")
        fault = st.text_area("Что случилось?", placeholder="Опишите неисправность")
        contact = st.text_input("Как с вами связаться?", placeholder="Телефон или почта")
        submitted = st.form_submit_button("Отправить заявку")

    if submitted:
        try:
            request = repository.create_request(device, fault, contact)
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state[ISSUED_NUMBER] = request.number

    number = st.session_state.get(ISSUED_NUMBER)
    if number:
        st.success("Заявка принята в работу.")
        st.markdown(f"**Номер заявки: {number}**")
        st.caption("Сохраните номер — по нему в любой момент видно текущий статус.")


def _render_lookup() -> None:
    with st.form("status_lookup", clear_on_submit=True):
        raw_number = st.text_input("Номер заявки", placeholder="2026-0001")
        submitted = st.form_submit_button("Показать статус")

    if not submitted:
        return

    view = repository.get_request_for_client(raw_number)
    if view is None:
        st.warning(
            "Заявки с таким номером у нас нет. Номер выглядит как 2026-0001 — "
            "проверьте, не потерялись ли цифры. Если номер верный, позвоните "
            "в мастерскую, разберёмся."
        )
        return
    _show_status(view)


def _show_status(view: RequestStatusView) -> None:
    st.markdown(f"### Заявка {view.number}")
    st.progress(view.status.position / (len(PIPELINE) - 1), text=view.status.value)
    st.caption(" → ".join(status.value for status in PIPELINE))
    st.write(f"**Обновлено:** {view.updated_at:%d.%m.%Y %H:%M}")
    if view.comment:
        st.write(f"**Комментарий мастера:** {view.comment}")
    else:
        st.caption("Комментария мастера пока нет.")
