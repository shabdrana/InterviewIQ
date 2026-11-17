"""Demo mode. The candidate answers below are SAMPLE text written for demonstration (and flagged as such).
They are evaluated by the real pipeline, so the scores you see are genuine engine output, not canned numbers."""
from __future__ import annotations

from . import db, service

DEMO_SETUP = {"interview_type": "General", "difficulty": "Intermediate", "experience_level": "Fresher",
              "domain": "Python", "num_questions": 5, "duration_min": 30, "instant_feedback": True}

DEMO_TURNS = [
    {"category": "behavioral", "difficulty": "Intermediate", "keywords": [],
     "q": "Tell me about a time you faced a tight deadline. How did you manage it?",
     "a": "During my final-year project, our team of four had two weeks to deliver a recommender app for a college fest. "
          "I was responsible for the backend API. I split the work into daily milestones, built the REST endpoints in Flask, "
          "and wrote unit tests so we wouldn't lose time on regressions. When the dataset loader turned out to be slow, I "
          "switched to batch loading, which cut start-up from 40 seconds to 6. As a result we shipped two days early, the demo "
          "scored 92% from the panel, and I learned to cut scope early instead of hoping to catch up."},
    {"category": "behavioral", "difficulty": "Intermediate", "keywords": [],
     "q": "Describe a conflict with a teammate and how you resolved it.",
     "a": "Um, so basically there was like a conflict in my team once, and I kind of talked to them, you know. I think it got "
          "better after that, I guess. We just sort of figured it out and, yeah, stuff like that."},
    {"category": "technical", "difficulty": "Intermediate", "keywords": ["WHERE", "HAVING", "GROUP BY", "aggregate", "filter", "rows"],
     "q": "What is the difference between WHERE and HAVING in SQL?",
     "a": "WHERE filters individual rows before any grouping happens, so it can't use aggregate functions. HAVING filters the "
          "groups produced by GROUP BY, after aggregation, so it can use things like COUNT or SUM. For example, to find "
          "departments with more than five employees I'd write WHERE name LIKE 'A%' to filter rows first, then GROUP BY "
          "department HAVING COUNT(*) > 5. Putting the row-level filter in WHERE is also cheaper because fewer rows get grouped."},
    {"category": "technical", "difficulty": "Intermediate", "keywords": ["mutable", "immutable", "tuple", "list", "hashable", "performance"],
     "q": "What is the difference between a list and a tuple in Python?",
     "a": "A tuple is mutable so you can change its items, while a list is immutable and can't be changed after creation. "
          "Lists use square brackets and tuples use round brackets. Both can hold different data types."},
    {"category": "hr", "difficulty": "Intermediate", "keywords": [],
     "q": "Why are you interested in working for our company?",
     "a": "I've followed your open-source data tools since my second year, and I contributed a small documentation fix to one of "
          "them last semester. I'm drawn to teams that ship reusable tooling, because my best learning came from building a "
          "library my classmates actually used. I'd like to grow into a backend engineer on a team that reviews code carefully."},
]


def run_demo(user_id: int, provider, progress=None) -> int:
    sid = service.start_interview(user_id, DEMO_SETUP, provider, is_demo=True)
    session = db.get_session(sid)
    setup = service.setup_of(session)
    for i, t in enumerate(DEMO_TURNS):
        if progress:
            progress(i, len(DEMO_TURNS))
        qid = db.add_question(sid, t["q"], category=t["category"], difficulty=t["difficulty"], source="bank",
                              expected_keywords=t["keywords"], transition="Sample question." if i else "Welcome to the demo interview.")
        aid = db.add_answer(qid, t["a"], 60)
        from .evaluator import evaluate_answer
        q = {"text": t["q"], "category": t["category"], "kind": "main", "expected_keywords": t["keywords"]}
        history = [r for r in db.conversation(sid) if r.get("answer_id") and r["answer_id"] != aid]
        db.save_ai_eval(aid, evaluate_answer(q, t["a"], setup, history, provider))
    service.finish_interview(sid, provider)
    return sid
