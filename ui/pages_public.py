"""Landing page and authentication."""
from __future__ import annotations

import streamlit as st

from core import auth, config
from . import theme
from .theme import html, icon


def _login_user(user: dict) -> None:
    st.session_state.user = user
    st.session_state.page = "mentor" if user["role"] == "mentor" else "dashboard"
    st.session_state.pop("active_sid", None)


def render_landing() -> None:
    c1, c2, c3 = st.columns([5, 1.3, 1.6])
    with c1:
        html(theme.brand())
    c2.button("Sign in", key="l_signin", on_click=theme.go, args=("auth",), use_container_width=True)
    c3.button("Create account", key="l_signup", type="primary", on_click=theme.go, args=("auth",), use_container_width=True)

    left, right = st.columns([1.15, 1], gap="large")
    with left:
        html(f"""<div class="hero hero-shell">{theme.badge("Mock interviews that listen", "info")}
        <h1>Practise interviews that <span class="grad-text">talk back.</span></h1>
        <p class="lead">A personal AI interviewer that listens to your answers, asks smart follow-ups,
        and turns every practice session into a clear improvement plan.</p>
        <div style="display:flex;gap:1.2rem;flex-wrap:wrap;margin-top:1.2rem;color:#A5B4D8;font-size:.82rem;font-weight:700">
          <span>✦ Adaptive questions</span><span>✦ Instant feedback</span><span>✦ Progress insights</span>
        </div></div>""")
        b1, b2, _ = st.columns([1.3, 1.3, 1])
        b1.button("Get started free", key="h_start", type="primary", on_click=theme.go, args=("auth",), use_container_width=True)
        if b2.button("Watch a demo", key="h_demo", use_container_width=True):
            from .pages_candidate import launch_demo
            launch_demo(auth.demo_user())
    with right:
        html("""<div class="hero-visual"><div class="orbit"></div><div class="hero-panel">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
          <span class="pill-live">Interview in progress</span><span class="muted small">02:48</span>
        </div>
        <div class="muted small">AI INTERVIEWER</div><h4 style="font-size:1.12rem;margin:.35rem 0 .9rem">Tell me about a challenge you solved with your team.</h4>
        <div style="display:flex;align-items:center;gap:9px;margin:.8rem 0 1rem">
          <div style="width:34px;height:34px;border-radius:11px;background:linear-gradient(135deg,#7C5CFF,#3B82F6);display:grid;place-items:center">✦</div>
          <div style="flex:1"><div style="font-size:.78rem;font-weight:700">Your answer is being evaluated</div><div class="muted" style="font-size:.7rem">Relevance · Clarity · Evidence</div></div>
          <span style="color:#6EE7B7;font-size:.78rem;font-weight:800">LIVE</span>
        </div>
        <div class="muted small">ANSWER QUALITY</div><div class="signal"><i style="width:84%"></i></div>
        <div style="display:flex;justify-content:space-between;font-size:.75rem"><span class="muted">Strong start</span><b style="color:#A5B4FC">84 / 100</b></div>
        </div></div>""")

    st.write("")
    f1, f2, f3 = st.columns(3)
    feats = [("message", "Follow-ups from your answers", "Vague claim? Missing result? The interviewer probes exactly that, and raises or lowers difficulty as you go."),
             ("target", "A transparent rubric", "Relevance, STAR structure, specificity, evidence, technical correctness, and filler or hedging. Every score comes with its reasoning."),
             ("shield", "Honest about its own scores", "AI and rule-based evaluations are always labelled. Mentor ratings are compared to AI scores with real statistics (MAE, correlation).")]
    for col, (ic, t, d) in zip((f1, f2, f3), feats):
        with col:
            theme.card(f'<div style="color:#A5B4FF">{icon(ic, 22)}</div><h4 style="margin-top:.6rem">{t}</h4><div class="muted small">{d}</div>', hover=True)

    st.write("")
    html("<h3>How a session works</h3>")
    steps = [("Set up", "Pick type, domain, difficulty and length."), ("Answer", "One question at a time, in your own words."),
             ("Get feedback", "Scores, what was missing, and a stronger example."), ("Track progress", "Compare attempts and see which skills improve.")]
    cols = st.columns(4)
    for i, (col, (t, d)) in enumerate(zip(cols, steps), 1):
        with col:
            theme.card(f'<div class="badge info">Step {i}</div><h4 style="margin-top:.6rem">{t}</h4><div class="muted small">{d}</div>')
    html('<div class="muted small" style="text-align:center;margin-top:1rem">InterviewIQ is a practice tool. Scores are feedback, not hiring decisions.</div>')


def render_auth() -> None:
    c1, c2 = st.columns([5, 1.2])
    with c1:
        html(theme.brand())
    c2.button("Back", key="a_back", on_click=theme.go, args=("landing",), use_container_width=True)
    _, mid, _ = st.columns([1, 1.5, 1])
    with mid:
        html('<div class="card"><h3 style="margin-top:0">Welcome to InterviewIQ</h3>'
             '<div class="muted small">Sign in to continue, or create an account to save your interview history.</div></div>')
        t_in, t_up = st.tabs(["Sign in", "Create account"])
        with t_in:
            with st.form("login_form"):
                email = st.text_input("Email", key="li_email")
                pw = st.text_input("Password", type="password", key="li_pw")
                ok = st.form_submit_button("Sign in", type="primary", use_container_width=True)
            if ok:
                fails = st.session_state.get("login_fails", 0)
                if fails >= 5:
                    st.error("Too many failed attempts. Refresh the page to try again.")
                else:
                    user, err = auth.login(email, pw)
                    if user:
                        st.session_state.login_fails = 0
                        _login_user(user)
                        st.rerun()
                    st.session_state.login_fails = fails + 1
                    st.error(err)
        with t_up:
            role_label = st.radio("I am a", ["Candidate", "Human evaluator (mentor)"], horizontal=True, key="su_role")
            with st.form("register_form"):
                name = st.text_input("Full name", key="su_name")
                email = st.text_input("Email", key="su_email")
                p1 = st.text_input("Password (8+ characters)", type="password", key="su_p1")
                p2 = st.text_input("Confirm password", type="password", key="su_p2")
                code = st.text_input("Evaluator access code", type="password", key="su_code",
                                     help="Only needed for evaluator accounts. Set MENTOR_ACCESS_CODE in .env.") \
                    if role_label.startswith("Human") else ""
                ok = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if ok:
                user, err = auth.register(name, email, p1, p2, "mentor" if role_label.startswith("Human") else "candidate", code)
                if user:
                    _login_user(user)
                    st.rerun()
                st.error(err)
