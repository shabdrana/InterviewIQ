"""Final report assembly: aggregates per-answer evaluations into dimension scores, analyses and a plan."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Optional

from . import llm
from .rubric import DIMENSIONS, LABELS, band

DIM_ADVICE = {
    "relevance": ("Answer the question first", "Start with a one-sentence direct answer, then support it. Re-read the question before you reply.",
                  "Practise answering 5 random questions in under 90 seconds each, opening with the direct answer."),
    "star": ("Structure behavioral stories with STAR", "Write each story as Situation, Task, Action, Result. Spend most of your words on Action and Result.",
             "Prepare four stories (teamwork, conflict, failure, initiative) and rehearse each in STAR order."),
    "specificity": ("Replace general claims with specifics", "Name the tool, number, person or decision. Swap 'things' and 'good' for exact terms.",
                    "Rewrite one of your answers and add three concrete details (a number, a tool, a name)."),
    "evidence": ("Back every claim with an example", "Give one real example and finish with a measurable outcome.",
                 "For each skill on your CV, write one sentence of proof with a result."),
    "technical": ("Strengthen technical depth", "Define the concept, show a small example, then mention a trade-off or pitfall. Review the concepts you missed.",
                  "Pick two topics from the missing-concepts list and explain each aloud as if teaching a junior."),
    "fluency": ("Cut filler and hedging", "Pause silently instead of using filler words and state what you know directly. Natural, conversational tone is fine.",
                "Record yourself answering and count fillers. Aim to halve the count each week."),
}


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 2) if xs else None


def threads(conv: list[dict]) -> list[dict]:
    """Group each main question with its follow-ups; thread score = mean of its answers' overall scores."""
    by_root: dict[int, list[dict]] = {}
    for r in conv:
        if not r.get("answer_id"):
            continue
        by_root.setdefault(r["parent_id"] or r["question_id"], []).append(r)
    out = []
    for root, rows in by_root.items():
        main = rows[0]
        out.append({"question": main["question"], "category": main["category"], "answer": main["answer"],
                    "score": round(sum(x["overall"] for x in rows) / len(rows), 1), "n_turns": len(rows),
                    "answer_id": main["answer_id"], "rows": rows})
    return out


def readiness(overall: float, dims: dict, n_answers: int) -> dict:
    scored = [v for v in dims.values() if v is not None]
    lowest = min(scored) if scored else 0
    if overall >= 80 and lowest >= 6:
        level, text = "Interview-ready", "Your answers are consistently strong. Keep practising under time pressure."
    elif overall >= 68:
        level, text = "Nearly ready", "You're close. Fix the weakest dimension below and you'll be competitive."
    elif overall >= 52:
        level, text = "Developing", "You have a base to build on. Follow the plan below for another 2-3 practice sessions."
    else:
        level, text = "Building foundations", "Focus on structure and specifics first. Short daily practice will move this quickly."
    caveat = ("Based on a small number of answers, so treat it as an indicative signal." if n_answers < 5 else "")
    return {"level": level, "text": text, "caveat": caveat}


def build_report(session: dict, conv: list[dict], provider: Optional[llm.Provider]) -> dict:
    answered = [r for r in conv if r.get("answer_id")]
    th = threads(conv)
    overall = _mean([t["score"] for t in th]) or 0.0
    dims = {d: _mean([r[d] for r in answered]) for d in DIMENSIONS}
    modes = {r["eval_mode"] for r in answered}
    mode = "llm" if modes == {"llm"} else "rule_based" if modes == {"rule_based"} else "mixed"

    ranked = sorted(th, key=lambda t: t["score"], reverse=True)
    k = min(3, max(1, len(ranked) // 2))
    pick = lambda t: {"question": t["question"], "answer": t["answer"][:400], "score": t["score"]}
    strongest, weakest = [pick(t) for t in ranked[:k]], [pick(t) for t in ranked[::-1][:k]]

    # communication
    langs = [r["details"]["language"] for r in answered if r.get("details")]
    fill = Counter()
    for l in langs:
        for p, c in l.get("fillers", []):
            fill[p] += c
    comm = {"avg_words": round(sum(r["word_count"] for r in answered) / max(1, len(answered)), 0),
            "short_answers": sum(1 for r in answered if r["word_count"] < 30),
            "avg_filler_pct": round(100 * (_mean([l["filler_rate"] for l in langs]) or 0), 1),
            "avg_hedge_pct": round(100 * (_mean([l["hedge_rate"] for l in langs]) or 0), 1),
            "top_fillers": fill.most_common(4), "fluency": dims["fluency"]}

    # technical
    tech_rows = [r for r in answered if r["category"] == "technical"]
    covered, missing, errors = Counter(), Counter(), []
    for r in tech_rows:
        t = (r.get("details") or {}).get("technical") or {}
        covered.update(t.get("covered", []))
        missing.update(t.get("missing", []))
        errors += t.get("errors", [])
    tech = {"n": len(tech_rows), "avg": dims["technical"], "strong_concepts": [c for c, _ in covered.most_common(5)],
            "missing_concepts": [c for c, _ in missing.most_common(6)], "errors": errors[:6]}

    # STAR
    beh = [r for r in answered if r["category"] == "behavioral" and (r.get("details") or {}).get("star", {}).get("applicable")]
    comp = {c: _mean([r["details"]["star"]["components"][c]["strength"] for r in beh]) for c in ("situation", "task", "action", "result")}
    star = {"n": len(beh), "components": comp, "avg": dims["star"],
            "weakest": min((c for c in comp if comp[c] is not None), key=lambda c: comp[c], default=None)}

    report = {"overall": overall, "band": band(overall), "dimensions": dims, "eval_mode": mode,
              "n_answers": len(answered), "n_questions": len(th), "strongest": strongest, "weakest": weakest,
              "communication": comm, "technical": tech, "star": star,
              "readiness": readiness(overall, dims, len(answered)),
              "generated_at": datetime.now().strftime("%d %b %Y, %H:%M")}
    report["plan"], report["plan_source"] = _plan(report, session, provider)
    return report


def _rule_plan(report: dict) -> list[dict]:
    ranked = sorted((d for d, v in report["dimensions"].items() if v is not None), key=lambda d: report["dimensions"][d])
    plan = []
    for d in ranked[:3]:
        if report["dimensions"][d] >= 8:
            continue
        focus, action, practice = DIM_ADVICE[d]
        extra = ""
        if d == "technical" and report["technical"]["missing_concepts"]:
            extra = " Concepts to review: " + ", ".join(report["technical"]["missing_concepts"][:4]) + "."
        plan.append({"focus": f"{LABELS[d]} ({report['dimensions'][d]:.1f}/10): {focus}", "why": "", "actions": [action + extra],
                     "practice": practice})
    return plan or [{"focus": "Maintain your standard", "why": "", "actions": ["Practise a harder difficulty level next."],
                     "practice": "Run an Advanced session and review the feedback."}]


def _plan(report, session, provider):
    if provider is not None:
        try:
            sys = ("You are an interview coach writing a short personalised improvement plan from aggregated rubric results. "
                   "Be specific, honest and encouraging, never invent scores. Return JSON: "
                   '{"plan": [{"focus": s, "why": s, "actions": [s, s], "practice": s}] (max 3 items, weakest areas first)}')
            user = (f"Interview: {session['interview_type']} ({session.get('domain') or 'general'}), {session['difficulty']}, "
                    f"level {session['experience_level']}\nOverall {report['overall']}/100\nDimension means (0-10, null=n/a): "
                    f"{report['dimensions']}\nSTAR component strengths (0-1): {report['star']['components']}\n"
                    f"Missing technical concepts: {report['technical']['missing_concepts']}; errors: {report['technical']['errors']}\n"
                    f"Communication: {report['communication']}")
            d = llm.complete_json(provider, sys, user, max_tokens=900)
            plan = [{"focus": str(p.get("focus", "")), "why": str(p.get("why", "")), "actions": [str(a) for a in p.get("actions", [])][:3],
                     "practice": str(p.get("practice", ""))} for p in d.get("plan", [])][:3]
            if plan:
                return plan, "llm"
        except Exception:
            pass
    return _rule_plan(report), "rule_based"
