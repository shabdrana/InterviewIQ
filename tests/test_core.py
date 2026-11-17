import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json  # noqa: E402

import pytest  # noqa: E402

from core import auth, db, evaluator, interviewer, llm, nlp, service, validation  # noqa: E402
from core.rubric import overall_score  # noqa: E402

db.init_db()
SETUP = {"interview_type": "Behavioral", "difficulty": "Intermediate", "experience_level": "Fresher", "domain": None,
         "num_questions": 2, "duration_min": 20, "instant_feedback": True}


def test_overall_renormalises_na_dimensions():
    full = {"relevance": 8, "star": 8, "specificity": 8, "evidence": 8, "technical": 8, "fluency": 8}
    assert overall_score(full) == 80.0
    assert overall_score({**full, "star": None, "technical": None}) == 80.0  # N/A neither helps nor hurts


def test_filler_detection_protects_technical_terms():
    lang = nlp.analyze_language("We filtered with WHERE name LIKE 'A%' and chose a kind of index suited to the query.")
    assert lang["filler_count"] == 0 and lang["hedge_weighted"] == 0
    assert "LIKE" in lang["protected_terms"]
    lang = nlp.analyze_language("Um, so basically it was, like, you know, fine.")
    assert lang["filler_count"] >= 4


def test_natural_style_is_not_penalised():
    text = ("I think the main idea is that a hash table maps keys to buckets, so lookups are fast. Actually, collisions "
            "are handled by chaining or open addressing, and the load factor decides when to resize the table.")
    assert nlp.fluency_score(nlp.analyze_language(text)) >= 8.5


def test_star_heuristic_detects_components():
    s = nlp.star_heuristic("When I was at my internship, I was responsible for the report. I built a script. As a result time dropped 40%.")
    c = s["components"]
    assert c["situation"]["strength"] > 0 and c["action"]["strength"] > 0 and c["result"]["strength"] > 0


def test_rule_based_is_labelled_and_never_claims_llm():
    q = {"text": "What is overfitting?", "category": "technical", "kind": "main", "expected_keywords": ["training", "validation"]}
    ev = evaluator.evaluate_answer(q, "Overfitting means the model memorises training data and fails on validation data.", SETUP, [], None)
    assert ev["eval_mode"] == "rule_based" and ev["model"] == "rules-v1" and ev["fallback_reason"]
    assert ev["details"]["technical"]["note"]


class FakeProvider(llm.Provider):
    name, model = "Fake", "fake-1"

    def __init__(self, reply):
        self.reply = reply

    def complete(self, system, user, max_tokens=1800):
        return self.reply


GOOD = {"scores": {"relevance": 8, "star": 7, "specificity": 6, "evidence": 7, "technical": 9, "fluency": 9},
        "reasoning": {"relevance": "ok"}, "star": {"situation": {"strength": 1}, "task": {"strength": 0.5}, "action": {"strength": 1},
                                                    "result": {"strength": 1}, "ownership_note": ""},
        "technical": {"covered": [], "missing": [], "errors": []}, "language_assessment": "fine",
        "feedback": {"did_well": ["a"], "missing": [], "weak_points": [], "improvements": ["b"], "stronger_example": "x", "next_tips": []},
        "follow_up": {"needed": True, "type": "followup", "question": "What was the result?"}}


def test_llm_path_parses_and_masks_non_applicable_dimensions():
    q = {"text": "Tell me about a time...", "category": "behavioral", "kind": "main", "expected_keywords": []}
    ev = evaluator.evaluate_answer(q, "I did a thing at work and it went well for the team.", SETUP, [], FakeProvider("```json\n" + json.dumps(GOOD) + "\n```"))
    assert ev["eval_mode"] == "llm" and ev["scores"]["technical"] is None  # N/A for behavioral even if the model returned a value
    assert ev["details"]["follow_up"]["needed"]


def test_llm_garbage_falls_back_honestly():
    q = {"text": "Q?", "category": "general", "kind": "main", "expected_keywords": []}
    ev = evaluator.evaluate_answer(q, "Some answer with enough words to evaluate properly here.", SETUP, [], FakeProvider("not json"))
    assert ev["eval_mode"] == "rule_based" and "failed" in ev["fallback_reason"]


def test_password_hashing_and_register_login():
    h = auth.hash_password("correct horse")
    assert auth.verify_password("correct horse", h) and not auth.verify_password("wrong", h)
    u, err = auth.register("Test User", "t@example.com", "password1", "password1")
    assert u and not err
    assert auth.register("Test User", "t@example.com", "password1", "password1")[0] is None  # duplicate
    assert auth.register("M", "m2@example.com", "password1", "password1", "mentor", "wrong-code")[0] is None
    assert auth.login("t@example.com", "password1")[0]["id"] == u["id"]


def test_adaptive_difficulty():
    assert interviewer.adapt_difficulty("Intermediate", [85, 80]) == "Advanced"
    assert interviewer.adapt_difficulty("Intermediate", [30, 40]) == "Beginner"
    assert interviewer.adapt_difficulty("Intermediate", [60]) == "Intermediate"


def test_full_session_flow_and_followups():
    u, _ = auth.register("Flow User", "flow@example.com", "password1", "password1")
    sid = service.start_interview(u["id"], SETUP, None)
    conv = db.conversation(sid)
    assert len(conv) == 1
    res = service.submit_answer(sid, conv[0]["question_id"], "I worked on it.", 10, None)
    assert res["next"] == "clarification"  # very thin answer -> clarification, not a static questionnaire
    conv = db.conversation(sid)
    assert conv[-1]["kind"] == "clarification" and conv[-1]["parent_id"] == conv[0]["question_id"]
    long = "At my internship I was responsible for a report. I built a script and as a result we saved 5 hours, and I learned a lot."
    res = service.submit_answer(sid, conv[-1]["question_id"], long, 40, None)
    assert res["next"] in ("main", "followup")
    rep = service.finish_interview(sid, None)
    assert rep and rep["eval_mode"] == "rule_based" and db.performance(u["id"])


def test_validation_metrics_use_only_real_ratings():
    assert validation.paired_frame("llm").empty  # nothing is invented
    u, _ = auth.register("Cand", "c3@example.com", "password1", "password1")
    mentor = db.get_user(db.create_user("mm@example.com", "Mentor", auth.hash_password("password1"), "mentor"))
    sid = service.start_interview(u["id"], SETUP, None)
    q = db.conversation(sid)[0]
    ids = []
    for i in range(6):
        qid = q["question_id"] if i == 0 else db.add_question(sid, f"Extra {i}", category="behavioral")
        aid = db.add_answer(qid, f"answer number {i} " * 10)
        from core.evaluator import evaluate_answer
        varied = {**GOOD, "scores": {**GOOD["scores"], "relevance": 4 + i, "evidence": 3 + i}}
        db.save_ai_eval(aid, evaluate_answer({"text": "Q", "category": "behavioral", "kind": "main", "expected_keywords": []},
                                             "answer " * 20, SETUP, [], FakeProvider(json.dumps(varied))))
        ids.append(aid)
    for i, aid in enumerate(ids):  # test-only human ratings
        sc = {"relevance": 6 + i % 3, "star": 6, "specificity": 5 + i % 2, "evidence": 6, "technical": None, "fluency": 8}
        db.save_human_eval(aid, mentor["id"], sc, overall_score(sc) - i * 2, "")
    df = validation.paired_frame("llm")
    s = validation.summarize(df)
    assert s["overall"]["n"] == 6 and s["overall"]["mae"] is not None and s["overall"]["pearson"] is not None
    assert validation.summarize(validation.paired_frame("rule_based"))["overall"]["n"] == 0
