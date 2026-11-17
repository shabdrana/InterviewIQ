"""InterviewIQ: AI-powered conversational interview coach. Run with:  streamlit run app.py"""
import streamlit as st

from core import db
from ui import theme
from ui.pages_candidate import (ai_badge, render_analytics, render_dashboard, render_feedback, render_history,
                                render_report, render_room, render_setup)
from ui.pages_evaluator import render_mentor
from ui.pages_public import render_auth, render_landing
from ui.pages_settings import render_settings

st.set_page_config(page_title="InterviewIQ", page_icon="🎯", layout="wide", initial_sidebar_state="expanded")
db.init_db()
theme.inject_css()

CANDIDATE_NAV = [("dashboard", "Dashboard", "dashboard"), ("setup", "New interview", "add_circle"), ("room", "Interview room", "forum"),
                 ("feedback", "Answer feedback", "rate_review"), ("report", "Final report", "description"),
                 ("analytics", "Analytics", "monitoring"), ("history", "History", "history"), ("settings", "Settings", "settings")]
MENTOR_NAV = [("mentor", "Evaluator dashboard", "fact_check"), ("settings", "Settings", "settings")]
PAGES = {"dashboard": render_dashboard, "setup": render_setup, "room": render_room, "feedback": render_feedback,
         "report": render_report, "analytics": render_analytics, "history": render_history, "mentor": render_mentor,
         "settings": render_settings}

user = st.session_state.get("user")
st.session_state.setdefault("page", "landing")

if not user:
    (render_auth if st.session_state.page == "auth" else render_landing)()
    st.stop()

nav = MENTOR_NAV if user["role"] == "mentor" else CANDIDATE_NAV
allowed = {k for k, _, _ in nav}
if st.session_state.page not in allowed:
    st.session_state.page = nav[0][0]

with st.sidebar:
    theme.html(theme.brand())
    for key, label, ic in nav:
        st.button(label, key=f"nav_{key}", icon=f":material/{ic}:", use_container_width=True,
                  type="primary" if st.session_state.page == key else "secondary", on_click=theme.go, args=(key,))
    st.write("")
    if user["role"] == "candidate":
        theme.html(ai_badge(user["id"]))
    theme.html(f"<div class='muted small' style='margin:.8rem 0 .4rem'>{user['full_name']}<br>{user['email']}</div>")
    if st.button("Log out", key="logout", icon=":material/logout:", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

PAGES[st.session_state.page](user)
