"""Orchestrates an interview: question flow, evaluation, follow-ups, adaptive difficulty, finishing."""
from __future__ import annotations

import json
from datetime import datetime

from . import db, interviewer, llm
from .evaluator import evaluate_answer
from .report import build_report, threads


def provider_for(user_id: int):
    prof = db.get_profile(user_id)
    return llm.get_provider(disabled=bool(prof.get("prefer_rule_based")))


def setup_of(session: dict) -> dict:
    return {k: session[k] for k in ("interview_type", "difficulty", "experience_level", "domain", "num_questions", "duration_min")}


def start_interview(user_id: int, setup: dict, provider, is_demo: bool = False) -> int:
    sid = db.create_session(user_id, setup, is_demo)
    if not is_demo:
        _add_main(sid, setup, provider, [], None, setup["difficulty"], 0)
    return sid


def _add_main(sid, setup, provider, asked, last_turn, difficulty, n_main) -> int:
    q = interviewer.next_main_question(setup, asked, last_turn, difficulty, provider, n_main)
    return db.add_question(sid, q["text"], kind="main", category=q["category"], difficulty=q["difficulty"], source=q["source"],
                           transition=q["transition"], expected_keywords=q["expected_keywords"])


def open_question(conv: list[dict]) -> dict | None:
    return next((r for r in reversed(conv) if not r.get("answer_id")), None)


def submit_answer(sid: int, qid: int, text: str, seconds: int | None, provider, time_up: bool = False) -> dict:
    session = db.get_session(sid)
    setup = setup_of(session)
    conv = db.conversation(sid)
    qrow = next(r for r in conv if r["question_id"] == qid)
    aid = db.add_answer(qid, text, seconds)
    q = {"text": qrow["question"], "category": qrow["category"], "kind": qrow["kind"], "expected_keywords": qrow["expected_keywords"]}
    history = [r for r in conv if r.get("answer_id")]
    ev = evaluate_answer(q, text, setup, history, provider)
    db.save_ai_eval(aid, ev)

    conv = db.conversation(sid)
    mains = [r for r in conv if r["kind"] == "main"]
    followups = [r for r in conv if r["kind"] != "main"]
    fu = ev["details"]["follow_up"]
    if (qrow["kind"] == "main" and fu["needed"] and not time_up and len(followups) < setup["num_questions"]):
        db.add_question(sid, fu["question"], kind=fu["type"], parent_id=qid, category=qrow["category"],
                        difficulty=qrow["difficulty"], source=fu["source"])
        return {"answer_id": aid, "eval": ev, "next": fu["type"]}
    if len(mains) < setup["num_questions"] and not time_up:
        th = threads(conv)
        diff = interviewer.adapt_difficulty(qrow["difficulty"], [t["score"] for t in th])
        last = {"question": qrow["question"], "answer": text}
        _add_main(sid, setup, provider, [r["question"] for r in conv], last, diff, len(mains))
        return {"answer_id": aid, "eval": ev, "next": "main", "difficulty": diff}
    return {"answer_id": aid, "eval": ev, "next": "done"}


def finish_interview(sid: int, provider) -> dict | None:
    session = db.get_session(sid)
    conv = db.conversation(sid)
    if not any(r.get("answer_id") for r in conv):
        db.update_session(sid, status="abandoned", ended_at=datetime.now().isoformat(timespec="seconds"))
        return None
    report = build_report(session, conv, provider)
    db.update_session(sid, status="completed", ended_at=datetime.now().isoformat(timespec="seconds"),
                      overall_score=report["overall"], eval_mode=report["eval_mode"], report_json=json.dumps(report))
    db.record_performance(sid, session["user_id"], {**session, "eval_mode": report["eval_mode"]}, report["overall"],
                          report["dimensions"])
    return report


def get_report(sid: int) -> dict | None:
    s = db.get_session(sid)
    return json.loads(s["report_json"]) if s and s.get("report_json") else None
