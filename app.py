import streamlit as st

from repair_service.config import PAGE_ICON, PAGE_TITLE, ROLE_CLIENT, ROLE_MASTER
from repair_service.db import init_db
from repair_service.views import client, master

st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")

init_db()

st.title(PAGE_TITLE)
st.caption("Приём заявки, статус ремонта, выдача.")

role = st.sidebar.radio("Кто вы?", [ROLE_CLIENT, ROLE_MASTER])

if role == ROLE_MASTER:
    master.render()
else:
    client.render()
