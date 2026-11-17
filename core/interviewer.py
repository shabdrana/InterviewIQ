"""The AI interviewer: lazily generates each main question (so difficulty can adapt to the
candidate's performance), and produces conversational transitions."""
from __future__ import annotations

import random
from typing import Optional

from . import llm
from .question_bank import BANK

LEVELS = ["Beginner", "Intermediate", "Advanced"]


def adapt_difficulty(current: str, recent_overall: list[float]) -> str:
    """Move one level up/down based on the average of the last two thread scores."""
    if not recent_overall:
        return current
    avg = sum(recent_overall[-2:]) / len(recent_overall[-2:])
    i = LEVELS.index(current) if current in LEVELS else 1
    if avg >= 75:
        i = min(2, i + 1)
    elif avg <= 45:
        i = max(0, i - 1)
    return LEVELS[i]


def category_for(interview_type: str, n_asked_main: int) -> str:
    if interview_type == "General":
        return ["hr", "behavioral", "general", "behavioral"][n_asked_main % 4]
    return {"HR": "hr", "Technical": "technical", "Behavioral": "behavioral"}.get(interview_type, "general")


def _bank_pick(setup: dict, category: str, difficulty: str, asked: list[str]) -> dict:
    domain = setup.get("domain")
    pool = [q for q in BANK if q["category"] == category and q["text"] not in asked
            and (category != "technical" or q["domain"] == domain)
            and (not q["experienced"] or setup["experience_level"] == "Experienced")]
    exact = [q for q in pool if q["difficulty"] == difficulty]
    near = sorted(pool, key=lambda q: abs(LEVELS.index(q["difficulty"]) - LEVELS.index(difficulty)))
    chosen = random.choice(exact) if exact else (near[0] if near else None)
    if chosen is None:  # bank exhausted: allow repeats of the category rather than failing
        chosen = random.choice([q for q in BANK if q["category"] == category] or BANK)
    return {"text": chosen["text"], "category": category, "difficulty": chosen["difficulty"],
            "expected_keywords": chosen["keywords"], "source": "bank", "transition": ""}


_SYSTEM = """You are a friendly but rigorous professional interviewer running a live mock interview.
Ask ONE question at a time. Questions must be realistic, unambiguous and suited to the candidate's level.
Never repeat a question already asked. Keep the optional 'transition' to one short, natural sentence that acknowledges
the candidate's previous answer (no scoring, no praise inflation); leave it empty for the first question.
Respond with JSON: {"question": str, "category": "hr|behavioral|technical|general", "difficulty": "Beginner|Intermediate|Advanced",
"expected_keywords": [up to 6 key concepts a good answer would cover], "transition": str}"""


def next_main_question(setup: dict, asked: list[str], last_turn: Optional[dict], difficulty: str,
                       provider: Optional[llm.Provider], n_main_asked: int) -> dict:
    category = category_for(setup["interview_type"], n_main_asked)
    if provider is not None:
        try:
            prev = ""
            if last_turn and last_turn.get("answer"):
                prev = f"Previous question: {last_turn['question']}\nCandidate's answer: {last_turn['answer'][:900]}\n"
            user = (f"Interview type: {setup['interview_type']}\nRequired category for this question: {category}\n"
                    f"Technical domain: {setup.get('domain') or 'n/a'}\nTarget difficulty: {difficulty}\n"
                    f"Candidate level: {setup['experience_level']}\nQuestions already asked: {asked}\n{prev}"
                    f"This is question {n_main_asked + 1} of {setup['num_questions']}.")
            d = llm.complete_json(provider, _SYSTEM, user, max_tokens=500)
            text = str(d["question"]).strip()
            if text and text not in asked:
                return {"text": text, "category": category,  # category is enforced by the interview type
                        "difficulty": d.get("difficulty") if d.get("difficulty") in LEVELS else difficulty,
                        "expected_keywords": [str(k) for k in d.get("expected_keywords", [])][:6],
                        "source": "llm", "transition": str(d.get("transition", "")).strip()}
        except Exception:
            pass  # silently fall through to the bank; the question's 'source' is recorded honestly
    q = _bank_pick(setup, category, difficulty, asked)
    if n_main_asked == 0:
        q["transition"] = "Thanks for joining. Let's get started."
    return q
