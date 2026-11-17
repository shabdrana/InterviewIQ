"""Settings / profile."""
from __future__ import annotations

import json

import streamlit as st

from core import auth, config, db, llm
from core.rubric import ANCHORS, DESCRIPTIONS, DIMENSIONS, LABELS, WEIGHTS
from . import theme
from .theme import html


def render_settings(user: dict) -> None:
    theme.page_header("Settings", "Your profile, security and AI engine.", "user")
    tabs = st.tabs(["Profile", "Account", "AI engine & rubric", "Data"])
    with tabs[0]:
        prof = db.get_profile(user["id"])
        with st.form("prof"):
            name = st.text_input("Full name", user["full_name"])
            if user["role"] == "candidate":
                c1, c2 = st.columns(2)
                college = c1.text_input("College / university", prof.get("college") or "")
                degree = c2.text_input("Degree", prof.get("degree") or "")
                c3, c4 = st.columns(2)
                year = c3.number_input("Graduation year", 2000, 2100, int(prof.get("grad_year") or 2026))
                role = c4.text_input("Target role", prof.get("target_role") or "")
                exp = st.radio("Experience level", config.EXPERIENCE_LEVELS, horizontal=True,
                               index=config.EXPERIENCE_LEVELS.index(prof.get("experience_level") or "Fresher"))
                skills = st.text_input("Key skills (comma separated)", prof.get("skills") or "")
                bio = st.text_area("About you", prof.get("bio") or "", height=90)
            ok = st.form_submit_button("Save profile", type="primary")
        if ok:
            if len(name.strip()) < 2:
                st.error("Enter your full name.")
            else:
                db.update_user(user["id"], full_name=name.strip())
                if user["role"] == "candidate":
                    db.save_profile(user["id"], college=college, degree=degree, grad_year=int(year), target_role=role,
                                    experience_level=exp, skills=skills, bio=bio)
                st.session_state.user = db.get_user(user["id"])
                st.toast("Profile saved")
    with tabs[1]:
        st.markdown(f"**Email:** {user['email']}  \n**Role:** {'Human evaluator' if user['role'] == 'mentor' else 'Candidate'}")
        with st.form("pw"):
            old = st.text_input("Current password", type="password")
            n1 = st.text_input("New password (8+ characters)", type="password")
            n2 = st.text_input("Confirm new password", type="password")
            ok = st.form_submit_button("Change password", type="primary")
        if ok:
            if not auth.verify_password(old, user["password_hash"]):
                st.error("Your current password is incorrect.")
            elif len(n1) < 8 or n1 != n2:
                st.error("Use at least 8 characters, and make sure both entries match.")
            else:
                db.update_user(user["id"], password_hash=auth.hash_password(n1))
                st.success("Password updated.")
    with tabs[2]:
        prov = llm.get_provider()
        if prov:
            html(theme.badge(f"Connected: {prov.label}", "ok"))
        else:
            html(theme.badge("No API key found. Rule-based mode is active.", "warn"))
            st.caption("Add ANTHROPIC_API_KEY or OPENAI_API_KEY to your .env file and restart the app. Rule-based results are always labelled.")
        if user["role"] == "candidate":
            prof = db.get_profile(user["id"])
            force = st.toggle("Always use rule-based mode (no API calls)", value=bool(prof.get("prefer_rule_based")), key="force_rb")
            if force != bool(prof.get("prefer_rule_based")):
                db.save_profile(user["id"], prefer_rule_based=int(force))
                st.rerun()
        if prov and st.button("Test connection", key="test_llm"):
            with st.spinner("Contacting the model..."):
                try:
                    st.success("Reply: " + prov.complete("Reply with the single word OK.", "ping", max_tokens=100).strip()[:40])
                except llm.LLMError as e:
                    st.error(str(e))
        html("<h4 style='margin-top:1rem'>Scoring rubric</h4>")
        for d in DIMENSIONS:
            with st.expander(f"{LABELS[d]} · weight {WEIGHTS[d]}%"):
                st.write(DESCRIPTIONS[d])
                for rng, txt in ANCHORS[d].items():
                    st.markdown(f"- **{rng}**: {txt}")
        st.caption("Overall = weighted mean of the dimensions that apply to the question, scaled to 100.")
    with tabs[3]:
        if user["role"] == "candidate":
            data = {"user": {k: user[k] for k in ("full_name", "email")}, "profile": db.get_profile(user["id"]),
                    "sessions": [{**s, "conversation": [{k: v for k, v in r.items() if k not in ("details_json",)} for r in db.conversation(s["id"])]}
                                 for s in db.list_sessions(user["id"])]}
            st.download_button("Export all my data (JSON)", json.dumps(data, indent=2, default=str), "interviewiq_my_data.json", "application/json", key="exp_json")
        html("<h4 style='margin-top:1rem;color:#FCA5A5'>Delete account</h4><div class='muted small'>Permanently removes your account, interviews and evaluations.</div>")
        if st.checkbox("I understand this cannot be undone", key="del_ok") and st.button("Delete my account", key="del_btn"):
            db.delete_user(user["id"])
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
