"""Candidate-facing pages: dashboard, setup, live room, feedback, report, analytics, history."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from html import escape

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core import analytics, config, db, demo, nlp, service
from core.pdf import report_pdf, transcript_text
from core.rubric import DIMENSIONS, LABELS, WEIGHTS, band
from . import theme
from .theme import html, icon


# ------------------------------------------------------------------ shared helpers
def ai_badge(user_id: int) -> str:
    p = service.provider_for(user_id)
    return theme.badge(f"AI engine: {p.label}", "ok") if p else theme.badge("Rule-based mode (no LLM connected)", "warn")


def launch_demo(user: dict) -> None:
    st.session_state.user = user
    prov = service.provider_for(user["id"])
    bar = st.progress(0, text="Running the sample interview through the real evaluator...")
    sid = demo.run_demo(user["id"], prov, progress=lambda i, n: bar.progress((i + 1) / n, text=f"Evaluating sample answer {i + 1} of {n}..."))
    st.session_state.update(view_sid=sid, page="report")
    st.rerun()


def _parse_utc(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _label(s: dict) -> str:
    n = f"{s['overall_score']:.0f}" if s.get("overall_score") is not None else "–"
    d = " · DEMO" if s["is_demo"] else ""
    return f"#{s['id']} · {s['interview_type']}{' ' + s['domain'] if s.get('domain') else ''} · {s['started_at'][:16]} · {n}{d}"


def _pick_session(user: dict, key: str, completed_only: bool = False) -> dict | None:
    sessions = [s for s in db.list_sessions(user["id"]) if s["status"] != "abandoned" and (s["status"] == "completed" or not completed_only)]
    if not sessions:
        return None
    ids = [s["id"] for s in sessions]
    want = st.session_state.get("view_sid") or st.session_state.get("active_sid")
    idx = ids.index(want) if want in ids else 0
    chosen = st.selectbox("Interview", sessions, index=idx, format_func=_label, key=key)
    st.session_state.view_sid = chosen["id"]
    return chosen


def _no_sessions(msg: str = "Complete your first interview to see this page.") -> None:
    theme.empty("Nothing here yet", msg)
    st.button("Start an interview", key=f"ns_{st.session_state.page}", type="primary", on_click=theme.go, args=("setup",))


def _first(name: str) -> str:
    return name.split()[0] if name else "there"


# ------------------------------------------------------------------ dashboard
def render_dashboard(user: dict) -> None:
    theme.page_header(f"Welcome back, {_first(user['full_name'])}", "Here is where your interview practice stands.", "layers")
    html(ai_badge(user["id"]))
    st.write("")
    perf = db.performance(user["id"])
    c = st.columns(4)
    n = len(perf)
    vals = [p["overall"] for p in perf]
    c[0].markdown(theme.kpi("Interviews completed", str(n), "excluding demo", "check"), unsafe_allow_html=True)
    c[1].markdown(theme.kpi("Average score", f"{sum(vals) / n:.0f}" if n else "–", "out of 100", "chart"), unsafe_allow_html=True)
    c[2].markdown(theme.kpi("Best score", f"{max(vals):.0f}" if n else "–", band(max(vals)) if n else "", "award"), unsafe_allow_html=True)
    delta = f"{vals[-1] - vals[-2]:+.0f} vs previous" if n > 1 else "latest attempt"
    c[3].markdown(theme.kpi("Latest score", f"{vals[-1]:.0f}" if n else "–", delta, "trend"), unsafe_allow_html=True)
    st.write("")
    a, b = st.columns([1.5, 1], gap="large")
    with a:
        theme.card("<h4>Score across sessions</h4>")
        if n:
            st.plotly_chart(analytics.overall_trend(perf), use_container_width=True, config={"displayModeBar": False})
        else:
            theme.empty("No sessions yet", "Your score trend will appear after your first completed interview.", "trend")
    with b:
        theme.card("<h4>Start practising</h4><div class='muted small'>Choose an interview type, a domain and a difficulty. "
                   "The interviewer adapts as you answer.</div>")
        st.button("Start new interview", key="d_new", type="primary", on_click=theme.go, args=("setup",), use_container_width=True)
        if st.button("Try the sample interview", key="d_demo", use_container_width=True):
            launch_demo(user)
        open_s = [s for s in db.list_sessions(user["id"]) if s["status"] == "in_progress" and not s["is_demo"]]
        if open_s:
            st.button(f"Resume interview #{open_s[0]['id']}", key="d_resume", on_click=theme.go, args=("room",),
                      kwargs={"active_sid": open_s[0]["id"]}, use_container_width=True)
    if n:
        dims = {d: db_mean([p[d] for p in perf]) for d in DIMENSIONS}
        st.write("")
        l, r = st.columns(2, gap="large")
        with l:
            theme.card("<h4>Where to focus next</h4>")
            st.plotly_chart(analytics.improvement_areas(dims), use_container_width=True, config={"displayModeBar": False})
        with r:
            theme.card("<h4>Recent interviews</h4>")
            for s in db.list_sessions(user["id"], include_demo=False)[:4]:
                if s["status"] != "completed":
                    continue
                x, y = st.columns([4, 1])
                x.markdown(f"**{s['interview_type']}{' · ' + s['domain'] if s.get('domain') else ''}** · {s['difficulty']}  \n"
                           f"<span class='muted small'>{s['started_at'][:16]} · {s['overall_score']:.0f}/100</span>", unsafe_allow_html=True)
                y.button("Open", key=f"d_open_{s['id']}", on_click=theme.go, args=("report",), kwargs={"view_sid": s["id"]})


def db_mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


# ------------------------------------------------------------------ setup
def render_setup(user: dict) -> None:
    theme.page_header("Start a new interview", "Tell the interviewer what you want to practise.", "target")
    prof = db.get_profile(user["id"])
    l, r = st.columns([1.4, 1], gap="large")
    with l:
        itype = st.radio("Interview type", config.INTERVIEW_TYPES, horizontal=True, key="su_type",
                         help="General mixes HR, behavioral and general questions.")
        c1, c2 = st.columns(2)
        diff = c1.select_slider("Starting difficulty", config.DIFFICULTIES, value="Intermediate", key="su_diff")
        exp = c2.radio("Experience level", config.EXPERIENCE_LEVELS, horizontal=True, key="su_exp",
                       index=config.EXPERIENCE_LEVELS.index(prof.get("experience_level") or "Fresher"))
        domain = st.selectbox("Technical domain", config.DOMAINS, key="su_dom", disabled=itype != "Technical",
                              help="Used for Technical interviews.")
        c3, c4 = st.columns(2)
        nq = c3.slider("Number of questions", 3, 10, 5, key="su_nq", help="Follow-up questions are extra.")
        dur = c4.slider("Duration (minutes)", 10, 60, 30, step=5, key="su_dur")
        instant = st.toggle("Show feedback after every answer", value=True, key="su_instant",
                            help="Turn off to simulate a real interview: feedback is revealed once you finish.")
    with r:
        theme.card(f"""<h4>Session summary</h4>
        <div class="muted small">Type</div><div><b>{itype}</b>{' · ' + domain if itype == 'Technical' else ''}</div><br>
        <div class="muted small">Starting difficulty</div><div><b>{diff}</b> <span class="muted small">(adapts to your answers)</span></div><br>
        <div class="muted small">Length</div><div><b>{nq} questions</b> · about {dur} min</div><br>
        <div class="muted small">Scoring engine</div><div>{ai_badge(user['id'])}</div>""")
        if itype == "Technical" and not service.provider_for(user["id"]):
            st.info("In rule-based mode, technical answers are scored on concept coverage only. Add an API key for correctness checking.")
        if st.button("Begin interview", key="su_go", type="primary", use_container_width=True):
            setup = {"interview_type": itype, "difficulty": diff, "experience_level": exp, "domain": domain if itype == "Technical" else None,
                     "num_questions": nq, "duration_min": dur, "instant_feedback": instant}
            with st.spinner("Your interviewer is preparing the first question..."):
                sid = service.start_interview(user["id"], setup, service.provider_for(user["id"]))
            st.session_state.active_sid = sid
            st.session_state.page = "room"
            st.rerun()


# ------------------------------------------------------------------ live room
def _bubble(role: str, text: str, meta: str) -> str:
    cls, av = ("me", icon("user", 16, "#C9D1F5")) if role == "me" else ("", icon("mic", 16, "#fff"))
    return (f'<div class="msg {cls}"><div class="av">{av}</div><div><div class="meta">{escape(meta)}</div>'
            f'<div class="bub">{escape(text).replace(chr(10), "<br>")}</div></div></div>')


def _timer(remaining: int) -> None:
    components.html(f"""<div style="font-family:Manrope,sans-serif;color:#E8ECFF;background:#121A33;border:1px solid #26315A;border-radius:12px;
    padding:8px 14px;display:inline-flex;gap:8px;align-items:center;font-weight:700">
    <span id="t" style="font-variant-numeric:tabular-nums">--:--</span><span style="color:#8B97C7;font-weight:600;font-size:12px">left</span></div>
    <script>let s={remaining};const e=document.getElementById('t');function f(){{const m=Math.floor(Math.max(s,0)/60),x=Math.max(s,0)%60;
    e.textContent=String(m).padStart(2,'0')+':'+String(x).padStart(2,'0');if(s<=0)e.style.color='#F87171';s--;}}f();setInterval(f,1000);</script>""", height=52)


def render_room(user: dict) -> None:
    sid = st.session_state.get("active_sid")
    session = db.get_session(sid) if sid else None
    if not session or session["user_id"] != user["id"]:
        theme.page_header("Interview room", "Your live conversation with the AI interviewer.", "mic")
        _no_sessions("Start an interview to enter the room.")
        return
    if session["status"] != "in_progress":
        theme.page_header("Interview room", "This interview is finished.", "mic")
        st.button("View final report", key="rm_rep", type="primary", on_click=theme.go, args=("report",), kwargs={"view_sid": sid})
        return

    provider = service.provider_for(user["id"])
    conv = db.conversation(sid)
    mains = [r for r in conv if r["kind"] == "main"]
    answered_mains = [r for r in mains if r.get("answer_id")]
    elapsed = (datetime.now(timezone.utc) - _parse_utc(session["started_at"])).total_seconds()
    remaining = int(session["duration_min"] * 60 - elapsed)
    theme.page_header("Live interview room", f"{session['interview_type']}{' · ' + session['domain'] if session.get('domain') else ''}", "mic")

    top = st.columns([3, 1])
    with top[0]:
        st.progress(min(1.0, len(answered_mains) / session["num_questions"]),
                    text=f"Question {min(len(mains), session['num_questions'])} of {session['num_questions']}")
        cur_diff = mains[-1]["difficulty"] if mains else session["difficulty"]
        html(ai_badge(user["id"]) + " " + theme.badge(f"Difficulty: {cur_diff}", "info") +
             " " + theme.badge("Feedback after each answer" if session["instant_feedback"] else "Feedback at the end"))
    with top[1]:
        _timer(max(remaining, 0))
    time_up = remaining <= 0
    if time_up:
        st.warning("Time limit reached. Submit your current answer to finish the interview.")

    st.write("")
    for r in conv:
        label = {"main": "Interviewer", "followup": "Interviewer · follow-up", "clarification": "Interviewer · clarification"}[r["kind"]]
        text = (r["transition"] + " " if r["transition"] and r["kind"] == "main" else "") + r["question"]
        html(_bubble("ai", text, label))
        if r.get("answer_id"):
            html(_bubble("me", r["answer"], f"You · {r['word_count']} words"))
            if session["instant_feedback"] and r.get("overall") is not None:
                chips = " · ".join(f"{LABELS[d].split(' ')[0]} {r[d]:.0f}" for d in DIMENSIONS if r[d] is not None)
                html(f'<div class="mini"><b style="color:#E8ECFF">{r["overall"]:.0f}/100</b> &nbsp;{escape(chips)}</div>')
                st.button("Full feedback", key=f"rm_fb_{r['answer_id']}", on_click=theme.go, args=("feedback",),
                          kwargs={"view_sid": sid, "view_aid": r["answer_id"]})

    open_q = service.open_question(conv)
    if open_q:
        qid = open_q["question_id"]
        st.session_state.setdefault(f"qstart_{qid}", time.time())
        with st.form(f"ans_{qid}", clear_on_submit=True):
            text = st.text_area("Your answer", height=170, key=f"txt_{qid}", label_visibility="collapsed",
                                placeholder="Answer as you would in the room. Aim for 60-150 words, with a real example where it fits.")
            go_btn = st.form_submit_button("Submit answer", type="primary")
        if go_btn:
            if len(text.split()) < 3:
                st.warning("Write at least a few words so the interviewer has something to respond to.")
            else:
                with st.spinner("Your interviewer is reviewing your answer..."):
                    res = service.submit_answer(sid, qid, text, int(time.time() - st.session_state[f"qstart_{qid}"]), provider, time_up)
                    if res["next"] == "done":
                        service.finish_interview(sid, provider)
                if res["next"] == "done":
                    st.session_state.update(view_sid=sid, page="report")
                st.rerun()
    c1, c2 = st.columns([1, 4])
    if c1.button("End interview", key="rm_end"):
        with st.spinner("Wrapping up..."):
            rep = service.finish_interview(sid, provider)
        if rep is None:
            db.delete_session(sid)
            st.session_state.page = "dashboard"
        else:
            st.session_state.update(view_sid=sid, page="report")
        st.rerun()


# ------------------------------------------------------------------ feedback
def render_feedback(user: dict) -> None:
    theme.page_header("Answer feedback", "Scores, reasoning and what to do next.", "bulb")
    session = _pick_session(user, "fb_sess")
    if not session:
        return _no_sessions("Answer a question in the interview room to see feedback.")
    if session["status"] == "in_progress" and not session["instant_feedback"]:
        theme.empty("Feedback is held until the end", "You chose realistic mode for this interview. Finish it to unlock every answer's feedback.", "clock")
        return
    rows = [r for r in db.conversation(session["id"]) if r.get("answer_id")]
    if not rows:
        return _no_sessions("This interview has no answered questions yet.")
    ids = [r["answer_id"] for r in rows]
    want = st.session_state.get("view_aid")
    r = st.selectbox("Answer", rows, index=ids.index(want) if want in ids else 0, key="fb_ans",
                     format_func=lambda x: f"Q{x['seq']} · {x['kind']} · {x['overall']:.0f}/100 · {x['question'][:60]}")
    d = r["details"]
    a, b = st.columns([1, 3])
    a.markdown(theme.ring(r["overall"]), unsafe_allow_html=True)
    with b:
        html(theme.mode_badge(r["eval_mode"]) + " " + theme.badge(band(r["overall"]), "info") + " " + theme.badge(f"{r['word_count']} words"))
        html(f"<h4 style='margin:.5rem 0 .2rem'>{escape(r['question'])}</h4>")
        html(f"<span class='muted small'>Engine: {escape(r['provider'] or '')} · {escape(r['model'] or '')}</span>")
    if r["eval_mode"] == "rule_based":
        st.warning((r.get("fallback_reason") or "Rule-based scoring.") + " These scores come from transparent heuristics, not from an LLM. "
                   "They measure vocabulary, structure cues and delivery, and cannot judge the meaning or correctness of your answer.")

    tabs = st.tabs(["Rubric scores", "STAR analysis", "Language", "Coaching", "Stronger answer"])
    with tabs[0]:
        l, rr = st.columns(2, gap="large")
        for i, dim in enumerate(DIMENSIONS):
            with (l if i % 2 == 0 else rr):
                theme.card(theme.dim_bar(dim, r[dim], (d["reasoning"].get(dim) or "") if r[dim] is not None else ""))
        wtxt = ", ".join(f"{LABELS[k].split(' ')[0]} {v}%" for k, v in WEIGHTS.items())
        html(f"<div class='muted small'>Overall = weighted mean of applicable dimensions ({wtxt}), "
             "re-normalised when STAR or technical correctness does not apply.</div>")
        if d.get("technical"):
            t = d["technical"]
            theme.card("<h4>Technical coverage</h4>" + f"<div class='small'><b>Covered:</b> {escape(', '.join(t.get('covered', [])) or 'none')}</div>"
                       f"<div class='small'><b>Missing:</b> {escape(', '.join(t.get('missing', [])) or 'none')}</div>"
                       + (f"<div class='small' style='color:#FCA5A5'><b>Errors found:</b> {escape('; '.join(t['errors']))}</div>" if t.get("errors") else "")
                       + (f"<div class='muted small'>{escape(t['note'])}</div>" if t.get("note") else ""))
    with tabs[1]:
        star = d.get("star") or {}
        if not star.get("applicable"):
            theme.empty("STAR doesn't apply here", "STAR is scored for behavioral questions, where a story is expected.", "layers")
        else:
            rowsh = ""
            for k, letter in zip(("situation", "task", "action", "result"), "STAR"):
                c = star["components"][k]
                cls = "star-ok" if c["strength"] >= 1 else "star-mid" if c["strength"] > 0 else "star-no"
                state = "Clear" if c["strength"] >= 1 else "Thin" if c["strength"] > 0 else "Missing"
                rowsh += (f'<div class="star-row"><div class="star-l {cls}">{letter}</div><div><b>{k.title()}</b> · {state}'
                          + (f'<div class="muted small">Found: {escape(c["evidence"])}</div>' if c.get("evidence") else "")
                          + (f'<div class="small">How to improve: {escape(c["improve"])}</div>' if c.get("improve") else "") + "</div></div>")
            theme.card(rowsh)
            if star.get("ownership_note"):
                st.info(star["ownership_note"])
    with tabs[2]:
        lang = d["language"]
        k1, k2, k3 = st.columns(3)
        k1.markdown(theme.kpi("Filler rate", f"{lang['filler_rate'] * 100:.1f}%", f"{lang['filler_count']} detected"), unsafe_allow_html=True)
        k2.markdown(theme.kpi("Hedging", f"{lang['hedge_rate'] * 100:.1f}%", "weighted rate"), unsafe_allow_html=True)
        k3.markdown(theme.kpi("Fluency score", f"{r['fluency']:.1f}", "out of 10"), unsafe_allow_html=True)
        st.write("")
        theme.card("<h4>Your answer with flagged phrases</h4><div class='small' style='line-height:1.7'>" + nlp.highlight_html(r["answer"], lang["spans"]) + "</div>"
                   "<div class='muted small' style='margin-top:.6rem'><mark class='mk-filler'>filler</mark> <mark class='mk-hedge'>hedge</mark>"
                   " &nbsp;Conversational style is tolerated. Only frequent filler or hedging lowers the score.</div>")
        if lang.get("protected_terms"):
            st.caption("Not counted as filler (technical terms): " + ", ".join(lang["protected_terms"]))
        if lang.get("assessment"):
            st.markdown(f"*{lang['assessment']}*")
    fb = d["feedback"]
    with tabs[3]:
        g1, g2 = st.columns(2, gap="large")
        with g1:
            theme.card(f'<h4 style="color:#6EE7B7">{icon("check", 16)} What you did well</h4>{theme.bullets(fb["did_well"])}')
            theme.card(f'<h4 style="color:#FCD34D">{icon("alert", 16)} Weak points</h4>{theme.bullets(fb["weak_points"])}')
        with g2:
            theme.card(f'<h4 style="color:#FCA5A5">{icon("target", 16)} What was missing</h4>{theme.bullets(fb["missing"])}')
            theme.card(f'<h4 style="color:#A5B4FF">{icon("zap", 16)} Suggested improvements</h4>{theme.bullets(fb["improvements"])}')
        theme.card(f"<h4>Tips for your next answer</h4>{theme.bullets(fb['next_tips'])}")
    with tabs[4]:
        theme.card(f"<h4>{escape(fb.get('stronger_example_label', 'Stronger answer'))}</h4><div style='line-height:1.65'>"
                   f"{escape(fb['stronger_example']).replace(chr(10), '<br>')}</div>")
    if session["status"] == "in_progress":
        st.button("Back to the interview room", key="fb_back", type="primary", on_click=theme.go, args=("room",), kwargs={"active_sid": session["id"]})


# ------------------------------------------------------------------ report
def render_report(user: dict) -> None:
    theme.page_header("Final performance report", "Your complete interview summary and improvement plan.", "award")
    session = _pick_session(user, "rp_sess")
    if not session:
        return _no_sessions()
    if session["status"] == "in_progress":
        theme.empty("This interview is still in progress", "Finish it to generate the report.", "clock")
        if st.button("Finish and generate report", key="rp_fin", type="primary"):
            with st.spinner("Building your report..."):
                service.finish_interview(session["id"], service.provider_for(user["id"]))
            st.rerun()
        return
    rep = service.get_report(session["id"])
    if not rep:
        st.warning("This interview has no report because no questions were answered.")
        return
    conv = db.conversation(session["id"])
    a, b = st.columns([1, 3])
    a.markdown(theme.ring(rep["overall"]), unsafe_allow_html=True)
    with b:
        html(theme.mode_badge(rep["eval_mode"]) + " " + theme.badge(rep["band"], "info") + (" " + theme.badge("Demo with sample answers", "warn") if session["is_demo"] else ""))
        html(f"<h3 style='margin:.5rem 0 .2rem'>Readiness: {escape(rep['readiness']['level'])}</h3><div class='muted'>{escape(rep['readiness']['text'])} {escape(rep['readiness']['caveat'])}</div>")
    if rep["eval_mode"] != "llm":
        st.warning("Some or all answers were scored by the rule-based fallback, not an LLM. Treat scores as structural feedback only.")
    d1, d2, _ = st.columns([1.3, 1.3, 3])
    d1.download_button("Download PDF", report_pdf(user["full_name"], session, rep), f"interviewiq_report_{session['id']}.pdf", "application/pdf", key="rp_pdf", use_container_width=True)
    d2.download_button("Transcript (.txt)", transcript_text(session, conv), f"interviewiq_transcript_{session['id']}.txt", key="rp_txt", use_container_width=True)

    t = st.tabs(["Overview", "Answers", "Communication", "Technical", "STAR", "Improvement plan"])
    with t[0]:
        l, r = st.columns([1, 1], gap="large")
        with l:
            theme.card("<h4>Dimension scores</h4>" + "".join(theme.dim_bar(d, rep["dimensions"][d]) for d in DIMENSIONS))
        with r:
            theme.card("<h4>Skill profile</h4>")
            st.plotly_chart(analytics.radar({"This interview": rep["dimensions"]}), use_container_width=True, config={"displayModeBar": False})
    with t[1]:
        for title, key, color in (("Strongest answers", "strongest", "#6EE7B7"), ("Weakest answers", "weakest", "#FCA5A5")):
            html(f"<h4 style='color:{color}'>{title}</h4>")
            for it in rep[key]:
                theme.card(f"<b>{it['score']:.0f}/100</b> · {escape(it['question'])}<div class='muted small' style='margin-top:.4rem'>{escape(it['answer'])}</div>")
    with t[2]:
        c = rep["communication"]
        k = st.columns(4)
        k[0].markdown(theme.kpi("Avg answer length", f"{c['avg_words']:.0f}", "words"), unsafe_allow_html=True)
        k[1].markdown(theme.kpi("Short answers", str(c["short_answers"]), "under 30 words"), unsafe_allow_html=True)
        k[2].markdown(theme.kpi("Filler rate", f"{c['avg_filler_pct']}%", "of words"), unsafe_allow_html=True)
        k[3].markdown(theme.kpi("Hedging", f"{c['avg_hedge_pct']}%", "weighted"), unsafe_allow_html=True)
        theme.card("<h4>Most frequent fillers</h4>" + (theme.bullets([f"{p} ×{n}" for p, n in c["top_fillers"]]) if c["top_fillers"] else "<span class='muted small'>None detected. Clean delivery.</span>"))
    with t[3]:
        tc = rep["technical"]
        if not tc["n"]:
            theme.empty("No technical questions", "Run a Technical interview to see concept coverage.", "layers")
        else:
            theme.card(f"<h4>Average technical score: {tc['avg']:.1f}/10 over {tc['n']} answer(s)</h4>"
                       f"<div class='small'><b>Strong concepts:</b> {escape(', '.join(tc['strong_concepts']) or '–')}</div>"
                       f"<div class='small'><b>Review these:</b> {escape(', '.join(tc['missing_concepts']) or 'nothing flagged')}</div>"
                       + (f"<div class='small' style='color:#FCA5A5'><b>Errors found:</b> {escape('; '.join(tc['errors']))}</div>" if tc["errors"] else ""))
            if rep["eval_mode"] != "llm":
                st.caption("Rule-based mode measures concept coverage only. It cannot detect incorrect statements.")
    with t[4]:
        s = rep["star"]
        if not s["n"]:
            theme.empty("No behavioral questions", "Run a Behavioral interview to see STAR analysis.", "layers")
        else:
            theme.card("<h4>Average strength of each STAR component</h4>" + "".join(
                f'<div class="dim"><div class="top"><span>{k.title()}</span><span>{(v or 0) * 100:.0f}%</span></div><div class="bar"><i style="width:{(v or 0) * 100:.0f}%"></i></div></div>'
                for k, v in s["components"].items()))
            if s["weakest"]:
                st.info(f"Your weakest component is **{s['weakest'].title()}**. Prioritise it in your next behavioral stories.")
    with t[5]:
        html(theme.badge("Written by AI" if rep["plan_source"] == "llm" else "Rule-based plan", "ok" if rep["plan_source"] == "llm" else "warn"))
        for p in rep["plan"]:
            theme.card(f"<h4>{escape(p['focus'])}</h4>" + (f"<div class='muted small'>{escape(p['why'])}</div>" if p["why"] else "") + theme.bullets(p["actions"])
                       + (f"<div class='small'><b>Practice:</b> {escape(p['practice'])}</div>" if p["practice"] else ""))


# ------------------------------------------------------------------ analytics
def render_analytics(user: dict) -> None:
    theme.page_header("Performance analytics", "How your interview skills change over time.", "trend")
    incl = st.toggle("Include demo sessions", value=False, key="an_demo")
    perf = db.performance(user["id"], include_demo=incl)
    if not perf:
        return _no_sessions("Complete an interview to unlock analytics.")
    modes = {p["eval_mode"] for p in perf}
    if len(modes) > 1:
        st.info("Your sessions mix LLM and rule-based scoring. Compare trends with care, because the two engines score differently.")
    theme.card("<h4>Overall score across sessions</h4>")
    st.plotly_chart(analytics.overall_trend(perf), use_container_width=True, config={"displayModeBar": False})
    a, b = st.columns(2, gap="large")
    with a:
        theme.card("<h4>Skill improvement by dimension</h4>")
        st.plotly_chart(analytics.skill_lines(perf), use_container_width=True, config={"displayModeBar": False})
    with b:
        theme.card("<h4>Technical vs behavioral performance</h4>")
        rows = [r for p in perf for r in db.conversation(p["session_id"]) if r.get("answer_id")]
        st.plotly_chart(analytics.technical_vs_behavioral(rows), use_container_width=True, config={"displayModeBar": False})
    c, d = st.columns(2, gap="large")
    with c:
        theme.card("<h4>Areas requiring improvement</h4>")
        st.plotly_chart(analytics.improvement_areas({k: db_mean([p[k] for p in perf]) for k in DIMENSIONS}), use_container_width=True, config={"displayModeBar": False})
    with d:
        theme.card("<h4>Compare two attempts</h4>")
        if len(perf) < 2:
            st.caption("Complete at least two interviews to compare attempts.")
        else:
            lab = lambda p: f"#{p['session_id']} · {p['interview_type']} · {p['overall']:.0f}"
            first = st.selectbox("Earlier", perf, index=0, format_func=lab, key="cmp_a")
            second = st.selectbox("Later", perf, index=len(perf) - 1, format_func=lab, key="cmp_b")
            st.plotly_chart(analytics.score_compare(first, second, f"#{first['session_id']}", f"#{second['session_id']}"), use_container_width=True, config={"displayModeBar": False})
            diff = second["overall"] - first["overall"]
            st.markdown(f"Overall change: **{diff:+.1f} points**")


# ------------------------------------------------------------------ history
def render_history(user: dict) -> None:
    theme.page_header("Interview history", "Every session you've run, newest first.", "clock")
    sessions = [s for s in db.list_sessions(user["id"]) if s["status"] != "abandoned"]
    if not sessions:
        return _no_sessions()
    f1, f2 = st.columns(2)
    types = f1.multiselect("Type", config.INTERVIEW_TYPES, key="hi_type")
    stat = f2.multiselect("Status", ["completed", "in_progress"], key="hi_stat")
    shown = [s for s in sessions if (not types or s["interview_type"] in types) and (not stat or s["status"] in stat)]
    df = pd.DataFrame([{"ID": s["id"], "Date": s["started_at"][:16], "Type": s["interview_type"], "Domain": s["domain"] or "–", "Difficulty": s["difficulty"],
                        "Score": s["overall_score"], "Engine": {"llm": "LLM", "rule_based": "Rule-based", "mixed": "Mixed"}.get(s["eval_mode"], "–"),
                        "Status": s["status"] + (" (demo)" if s["is_demo"] else "")} for s in shown])
    st.dataframe(df, hide_index=True, use_container_width=True, column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.0f")})
    st.download_button("Export history (CSV)", df.to_csv(index=False), "interviewiq_history.csv", "text/csv", key="hi_csv")
    st.write("")
    html("<h4>Actions</h4>")
    for s in shown[:25]:
        c = st.columns([5, 1.2, 1.2, 1])
        c[0].markdown(f"**#{s['id']}** {s['interview_type']}{' · ' + s['domain'] if s['domain'] else ''} <span class='muted small'>· {s['started_at'][:16]}</span>", unsafe_allow_html=True)
        if s["status"] == "completed":
            c[1].button("Report", key=f"hi_r_{s['id']}", on_click=theme.go, args=("report",), kwargs={"view_sid": s["id"]}, use_container_width=True)
            c[2].button("Answers", key=f"hi_f_{s['id']}", on_click=theme.go, args=("feedback",), kwargs={"view_sid": s["id"], "view_aid": None}, use_container_width=True)
        else:
            c[1].button("Resume", key=f"hi_s_{s['id']}", on_click=theme.go, args=("room",), kwargs={"active_sid": s["id"]}, use_container_width=True)
        if c[3].button("Delete", key=f"hi_d_{s['id']}", use_container_width=True):
            db.delete_session(s["id"])
            st.rerun()
