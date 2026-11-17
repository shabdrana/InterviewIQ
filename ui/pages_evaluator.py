"""Human evaluator dashboard: blind rating with the same rubric + AI-vs-human agreement statistics."""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from core import analytics, db, validation
from core.rubric import ANCHORS, DIMENSIONS, LABELS, applicable_dimensions, overall_score
from . import theme
from .theme import html


def render_mentor(user: dict) -> None:
    theme.page_header("Human evaluator", "Rate real candidate answers with the same rubric, then compare with the AI.", "shield")
    t1, t2 = st.tabs(["Review answers", "Agreement analysis"])
    with t1:
        _review(user)
    with t2:
        _analysis()


def _review(user: dict) -> None:
    items = db.reviewable_answers(user["id"])
    if not items:
        theme.empty("No candidate answers to review yet", "Answers from real (non-demo) interviews appear here once candidates complete them.")
        return
    f1, f2 = st.columns(2)
    mode = f1.selectbox("Scoring engine of the AI result", ["All", "llm", "rule_based"], format_func=lambda m: {"All": "All", "llm": "LLM", "rule_based": "Rule-based"}[m], key="ev_mode")
    only_new = f2.toggle("Only answers I haven't rated", value=True, key="ev_new")
    items = [i for i in items if (mode == "All" or i["eval_mode"] == mode) and (not only_new or not i["rated_by_me"])]
    if not items:
        st.success("You've rated everything in this filter.")
        return
    sel = st.selectbox("Answer", items, key="ev_sel", format_func=lambda i: f"A{i['answer_id']} · {i['category']} · {i['question'][:70]}" + (" ✓" if i["rated_by_me"] else ""))
    mine = db.get_human_eval(sel["answer_id"], user["id"])
    app = applicable_dimensions(sel["category"])

    l, r = st.columns([1.25, 1], gap="large")
    with l:
        theme.card(f"<div class='muted small'>Candidate (anonymised) · {escape(sel['interview_type'])}{' · ' + escape(sel['domain']) if sel['domain'] else ''}</div>"
                   f"<h4 style='margin-top:.4rem'>{escape(sel['question'])}</h4><div style='line-height:1.65'>{escape(sel['answer']).replace(chr(10), '<br>')}</div>")
        if not mine:
            st.info("Blind review: the AI's scores are hidden until you save your own ratings.")
    with r:
        with st.form(f"hf_{sel['answer_id']}"):
            html("<h4 style='margin:0 0 .4rem'>Your ratings (0-10)</h4>")
            scores = {}
            for d in DIMENSIONS:
                if not app[d]:
                    scores[d] = None
                    continue
                default = float(mine[d]) if mine and mine[d] is not None else 5.0
                scores[d] = st.slider(LABELS[d], 0.0, 10.0, default, 0.5, key=f"hs_{sel['answer_id']}_{d}",
                                      help=" | ".join(f"{k}: {v}" for k, v in ANCHORS[d].items()))
            comments = st.text_area("Comments", value=(mine or {}).get("comments") or "", key=f"hc_{sel['answer_id']}", height=100)
            ok = st.form_submit_button("Save ratings", type="primary", use_container_width=True)
        if ok:
            db.save_human_eval(sel["answer_id"], user["id"], scores, overall_score(scores), comments)
            st.toast("Ratings saved")
            st.rerun()

    if mine:
        ai = db.get_ai_eval(sel["answer_id"])
        rows = [{"Dimension": LABELS[d], "Human": mine[d], "AI": ai[d], "Difference (AI − human)": None if mine[d] is None or ai[d] is None else round(ai[d] - mine[d], 1)}
                for d in DIMENSIONS if app[d]]
        rows.append({"Dimension": "Overall (0-100)", "Human": mine["overall"], "AI": ai["overall"], "Difference (AI − human)": round(ai["overall"] - mine["overall"], 1)})
        html("<h4>Comparison</h4>")
        html(theme.mode_badge(ai["eval_mode"]))
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        with st.expander("AI reasoning"):
            for d in DIMENSIONS:
                if app[d] and ai["details"]["reasoning"].get(d):
                    st.markdown(f"**{LABELS[d]}:** {ai['details']['reasoning'][d]}")


def _analysis() -> None:
    mode = st.radio("AI engine to validate", ["llm", "rule_based"], horizontal=True, key="va_mode",
                    format_func=lambda m: "LLM evaluations" if m == "llm" else "Rule-based evaluations",
                    help="Validated separately, because the two engines are different instruments.")
    df = validation.paired_frame(mode)
    if df.empty:
        theme.empty("No human ratings yet", "Nothing is estimated or simulated. Statistics appear only after evaluators rate real answers in the Review tab.", "chart")
        return
    s = validation.summarize(df)
    o = s["overall"]
    f = lambda v, nd=2: "–" if v is None else f"{v:.{nd}f}"
    k = st.columns(5)
    k[0].markdown(theme.kpi("Rated answers", str(o["n"]), "human-rated"), unsafe_allow_html=True)
    k[1].markdown(theme.kpi("MAE (overall)", f(o["mae"], 1), "points of 100"), unsafe_allow_html=True)
    k[2].markdown(theme.kpi("Bias", "–" if o["bias"] is None else f"{o['bias']:+.1f}", "AI − human"), unsafe_allow_html=True)
    k[3].markdown(theme.kpi("Pearson r", f(o["pearson"]), "overall"), unsafe_allow_html=True)
    k[4].markdown(theme.kpi("Spearman ρ", f(o["spearman"]), "rank agreement"), unsafe_allow_html=True)
    if o["n"] < validation.MIN_FOR_CORRELATION:
        st.info(f"Correlation needs at least {validation.MIN_FOR_CORRELATION} rated answers. MAE is shown from the first rating.")
    elif o["n"] < 30:
        st.warning("Small sample: treat these statistics as preliminary. 30 or more rated answers gives a steadier picture.")
    a, b = st.columns(2, gap="large")
    with a:
        theme.card("<h4>AI vs human overall score</h4>")
        st.plotly_chart(analytics.ai_vs_human_scatter(df), use_container_width=True, config={"displayModeBar": False})
    with b:
        theme.card("<h4>Score differences per answer</h4>")
        st.plotly_chart(analytics.difference_bars(df), use_container_width=True, config={"displayModeBar": False})
    rows = [{"Dimension": LABELS[d], "n": m["n"], "MAE (0-10)": m["mae"], "Bias (AI−human)": m["bias"], "Pearson r": m["pearson"], "Spearman ρ": m["spearman"]}
            for d, m in s["dimensions"].items()]
    html("<h4>Per-dimension agreement</h4>")
    st.dataframe(pd.DataFrame(rows).round(2), hide_index=True, use_container_width=True)
    st.download_button("Export paired scores (CSV)", df.round(2).to_csv(index=False), "interviewiq_ai_vs_human.csv", "text/csv", key="va_csv")
    st.caption("Per answer, human scores are averaged across evaluators. Demo sessions are excluded. MAE = mean |AI − human|.")
