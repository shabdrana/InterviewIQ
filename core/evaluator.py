"""Answer evaluation against the six-dimension rubric.

Two engines, never mixed up:
  * LLM mode        -> eval_mode == 'llm'         (real model judgement, with reasoning)
  * Rule-based mode -> eval_mode == 'rule_based'  (transparent heuristics; labelled everywhere in the UI)
The overall score is always computed in code from the dimension scores and rubric weights."""
from __future__ import annotations

import re
from typing import Optional

from . import llm, nlp
from .rubric import DIMENSIONS, applicable_dimensions, overall_score, rubric_text

_clamp = lambda x, lo=0.0, hi=10.0: max(lo, min(hi, float(x)))


# ====================================================================== public entry point
def evaluate_answer(question: dict, answer: str, setup: dict, history: list[dict],
                    provider: Optional[llm.Provider]) -> dict:
    """question: dict with text/category/expected_keywords/kind. history: earlier turns of this session."""
    lang = nlp.analyze_language(answer)
    reason = None
    if provider is not None:
        try:
            return _llm_eval(question, answer, setup, history, provider, lang)
        except Exception as e:  # network, auth, bad JSON...
            reason = f"LLM evaluation failed ({str(e)[:160]}). Rule-based scoring was used instead."
    else:
        reason = "No LLM available (no API key, or rule-based mode selected)."
    ev = _rule_eval(question, answer, lang)
    ev["fallback_reason"] = reason
    return ev


# ====================================================================== LLM engine
_SYSTEM = """You are an expert interview coach scoring ONE candidate answer with a fixed rubric.

RUBRIC (score each applicable dimension 0-10, one decimal allowed):
{rubric}

RULES
- Score only what is in the answer. Do not reward length for its own sake. Do not invent facts about the candidate.
- STAR applies only if question category is 'behavioral'; technical correctness only if category is 'technical'.
  For non-applicable dimensions return null.
- Do NOT penalise a natural, conversational speaking style. Filler/hedging counts only when it is frequent enough to
  weaken the message. Technical vocabulary is never filler (e.g. SQL "LIKE", "just-in-time", "kind of index").
- Technical correctness: actively look for factual errors and state them explicitly in the reasoning.
- 'reasoning' must justify each score in one or two concrete sentences referring to the answer.
- 'stronger_example' is an illustrative model answer built on the candidate's own content and the question;
  where the candidate gave no real facts use placeholders like [metric] rather than inventing details.
- 'follow_up': decide like a real interviewer. needed=true only if there is something worth probing (vague claim,
  missing result, interesting technical point) or the answer is too thin (type 'clarification'). Otherwise needed=false.

Return JSON with exactly these keys:
{{"scores": {{"relevance": n, "star": n|null, "specificity": n, "evidence": n, "technical": n|null, "fluency": n}},
 "reasoning": {{"relevance": s, "star": s|null, "specificity": s, "evidence": s, "technical": s|null, "fluency": s}},
 "star": {{"situation": {{"strength": 0-1, "evidence": s, "improve": s}}, "task": {{...}}, "action": {{...}}, "result": {{...}},
          "ownership_note": s}} | null,
 "technical": {{"covered": [concepts], "missing": [concepts], "errors": [explicit incorrect statements]}} | null,
 "language_assessment": s,
 "feedback": {{"did_well": [s], "missing": [s], "weak_points": [s], "improvements": [s], "stronger_example": s,
              "next_tips": [s]}},
 "follow_up": {{"needed": bool, "type": "followup"|"clarification", "question": s}}}}"""


def _llm_eval(q, answer, setup, history, provider, lang) -> dict:
    cat = q.get("category", "general")
    recent = "\n".join(f"Q: {h['question']}\nA: {(h.get('answer') or '')[:300]}" for h in history[-3:] if h.get("answer"))
    user = (f"Interview: {setup['interview_type']} | difficulty {setup['difficulty']} | level {setup['experience_level']}"
            f" | domain {setup.get('domain') or 'n/a'}\nQuestion category: {cat}\nQuestion kind: {q.get('kind', 'main')}\n"
            f"Question: {q['text']}\nKey concepts a good answer may cover: {q.get('expected_keywords') or 'not specified'}\n"
            f"Earlier turns (context only):\n{recent or '(none)'}\n\n"
            f"Regex-detected filler/hedging (objective counts, you decide if it matters): fillers={lang['fillers']}, "
            f"hedges={lang['hedges']}, words={lang['word_count']}\n\nCANDIDATE ANSWER:\n\"\"\"\n{answer}\n\"\"\"")
    d = llm.complete_json(provider, _SYSTEM.format(rubric=rubric_text()), user, max_tokens=2200)

    app = applicable_dimensions(cat)
    raw = d.get("scores") or {}
    scores = {}
    for dim in DIMENSIONS:
        if not app[dim]:
            scores[dim] = None
        else:
            if raw.get(dim) is None:
                raise llm.LLMError(f"Missing score for '{dim}'.")
            scores[dim] = round(_clamp(raw[dim]), 1)
    reasoning = {k: (str(v) if v else "") for k, v in (d.get("reasoning") or {}).items()}
    fb = d.get("feedback") or {}
    feedback = {k: [str(x) for x in fb.get(k, [])][:6] for k in ("did_well", "missing", "weak_points", "improvements", "next_tips")}
    feedback["stronger_example"] = str(fb.get("stronger_example", ""))
    feedback["stronger_example_label"] = "Illustrative model answer written by the AI. Adapt it to your real experience."

    star = None
    if app["star"]:
        s = d.get("star") or {}
        comps = {}
        for k in ("situation", "task", "action", "result"):
            c = s.get(k) or {}
            comps[k] = {"strength": round(_clamp(c.get("strength", 0), 0, 1), 2), "evidence": str(c.get("evidence", "")),
                        "improve": str(c.get("improve", ""))}
        star = {"applicable": True, "components": comps, "ownership_note": str(s.get("ownership_note", "") or "")}
    tech = d.get("technical") if app["technical"] else None
    fu = d.get("follow_up") or {}
    follow = {"needed": bool(fu.get("needed")) and bool(str(fu.get("question", "")).strip()),
              "type": "clarification" if fu.get("type") == "clarification" else "followup",
              "question": str(fu.get("question", "")).strip(), "source": "llm"}
    details = {"reasoning": reasoning, "star": star or {"applicable": False}, "technical": tech,
               "language": {**lang, "assessment": str(d.get("language_assessment", ""))},
               "feedback": feedback, "follow_up": follow}
    return {"eval_mode": "llm", "provider": provider.name, "model": provider.model, "fallback_reason": None,
            "scores": scores, "overall": overall_score(scores), "details": details}


# ====================================================================== rule-based engine
_VAGUE = re.compile(r"\b(?:thing|things|stuff|somehow|etc|whatever|a lot of|lots of|good|nice|bad|many|several|various|"
                    r"really|very)\b", re.I)
_EXAMPLE = re.compile(r"\b(?:for example|for instance|such as|e\.g\.|one time|in my (?:project|internship|team|college)|"
                      r"at my|when i|we built|i built|i worked)\b", re.I)
_RESULT = re.compile(r"\b(?:result|outcome|improved|reduced|increased|saved|achieved|delivered|learned|won|launched|"
                     r"finished|passed|success)\w*\b", re.I)
_NUM = re.compile(r"\b\d+(?:\.\d+)?\s?(?:%|percent|x|ms|seconds|hours|days|weeks|months|users|people|members|k)?\b")


_RELATED = {  # topic words in common behavioral/HR prompts -> words that show the answer is on topic
    "deadline": "deadline milestone schedule weeks days tight deliver shipped prioritize time urgent",
    "conflict": "conflict disagree disagreement tension argue perspective compromise mediate talked listened",
    "mistake": "mistake error wrong fix fixed learned lesson responsibility apologized",
    "team": "team teammate teammates colleague colleagues collaborate group together members",
    "learn": "learn learned course tutorial practice documentation self-taught studied",
    "initiative": "initiative proposed volunteered noticed started suggested ownership",
    "strength": "strength strong good skilled ability helped",
    "weakness": "weakness improve improving working learning struggle practice",
    "feedback": "feedback listened suggestion criticism reviewed improved",
    "fail": "fail failed failure shortfall missed lesson changed",
    "motivate": "motivated motivation passion enjoy interest excited",
    "company": "company team product mission values culture role",
    "role": "role responsibilities skills team company growth",
    "years": "goal grow growth career skills lead learn",
}


def _relevance(q, answer, wc):
    ans = nlp.stems(answer)
    qs = nlp.stems(q["text"], drop_generic=True)
    hits = 0
    for t in qs:
        related = {t}
        for topic, words in _RELATED.items():
            if nlp._stem(topic) == t:
                related |= nlp.stems(words)
        hits += bool(related & ans)
    cov_q = hits / len(qs) if qs else 0.5
    kws = q.get("expected_keywords") or []
    if kws:
        hit, _ = nlp.keyword_hits(answer, kws)
        raw = 0.3 * min(1, cov_q / 0.5) + 0.7 * min(1, (len(hit) / len(kws)) / 0.6)
        s = 10 * raw
    else:  # no reference concepts: vocabulary overlap is a weak signal, so keep a modest floor
        s = 3.5 + 6.5 * min(1, cov_q / 0.4)
    if wc < 15:
        s = min(s, 3.5)
    elif wc < 30:
        s = min(s, 6.0)
    return round(_clamp(s), 1)


def _specificity(answer, wc):
    nums = len(_NUM.findall(answer))
    names = sum(1 for s in nlp.sentences(answer) for w in s.split()[1:] if re.match(r"^[A-Z][a-zA-Z0-9+#]+$", w) and w != "I")
    vague = len(_VAGUE.findall(answer))
    sents = nlp.sentences(answer) or [answer]
    avg_len = wc / len(sents)
    s = 3.0 + min(3.0, nums) + min(2.5, names * 0.5) + min(1.5, avg_len / 12) - min(3.0, vague * 0.7)
    if wc < 20:
        s = min(s, 3.0)
    elif wc < 40:
        s = min(s, 5.5)
    return round(_clamp(s), 1)


def _evidence(answer, wc):
    ex, res, nums = len(_EXAMPLE.findall(answer)), len(_RESULT.findall(answer)), len(_NUM.findall(answer))
    s = 1.5 + 2.0 * min(2, ex) + 1.5 * min(2, res) + 1.0 * min(2, nums)
    if wc < 20:
        s = min(s, 3.0)
    return round(_clamp(s), 1)


def _rule_eval(q, answer, lang) -> dict:
    cat = q.get("category", "general")
    app = applicable_dimensions(cat)
    wc = lang["word_count"]
    kws = q.get("expected_keywords") or []
    scores, reasoning = {}, {}

    scores["relevance"] = _relevance(q, answer, wc)
    reasoning["relevance"] = ("Estimated from how many key terms of the question" + (" and expected concepts" if kws else "")
                              + " appear in your answer. This cannot judge meaning, only vocabulary overlap.")
    star = {"applicable": False}
    if app["star"]:
        star = nlp.star_heuristic(answer)
        scores["star"] = nlp.star_score(star)
        present = [k.title() for k, v in star["components"].items() if v["strength"] >= 1]
        reasoning["star"] = f"Detected STAR cues for: {', '.join(present) or 'none'}. Cue-based, so unusual phrasing may be missed."
    else:
        scores["star"], reasoning["star"] = None, None
    scores["specificity"] = _specificity(answer, wc)
    reasoning["specificity"] = "Based on numbers, named tools/people, sentence length and vague words such as 'stuff' or 'things'."
    scores["evidence"] = _evidence(answer, wc)
    reasoning["evidence"] = "Based on example phrases ('for example', 'in my project'), outcome words and quantified results."

    tech = None
    if app["technical"]:
        if kws:
            hit, miss = nlp.keyword_hits(answer, kws)
            scores["technical"] = round(_clamp(10 * len(hit) / len(kws) * 1.15), 1)
            tech = {"covered": hit, "missing": miss, "errors": [],
                    "note": "Rule-based mode only measures concept coverage. It CANNOT detect incorrect statements."}
            reasoning["technical"] = (f"Covered {len(hit)} of {len(kws)} expected concepts. Coverage estimate only: "
                                      "factual errors are not detected in rule-based mode.")
        else:
            scores["technical"], reasoning["technical"] = None, "No reference concepts available, so technical correctness was not scored."
    else:
        scores["technical"], reasoning["technical"] = None, None
    scores["fluency"] = nlp.fluency_score(lang)
    reasoning["fluency"] = (f"{lang['filler_count']} filler(s) and {lang['hedge_weighted']} weighted hedge(s) in {wc} words. "
                            "About 2% filler and 3% hedging are tolerated; code and technical terms are ignored.")

    fb = _rule_feedback(q, answer, scores, star, tech, lang, wc)
    fu = _rule_follow_up(q, answer, scores, star, tech, wc)
    details = {"reasoning": reasoning, "star": star, "technical": tech,
               "language": {**lang, "assessment": ""}, "feedback": fb, "follow_up": fu}
    return {"eval_mode": "rule_based", "provider": "Built-in heuristics", "model": "rules-v1", "fallback_reason": None,
            "scores": scores, "overall": overall_score(scores), "details": details}


def _rule_feedback(q, answer, scores, star, tech, lang, wc) -> dict:
    well, missing, weak, impr, tips = [], [], [], [], []
    if scores["relevance"] >= 7:
        well.append("Your answer stays close to the question.")
    if scores["specificity"] >= 7:
        well.append("You used concrete details (numbers, names or tools).")
    if scores["evidence"] >= 7:
        well.append("You backed your points with an example or outcome.")
    if scores["fluency"] >= 8:
        well.append("Your delivery is clean and confident.")
    if tech and len(tech["covered"]) >= max(2, len(tech["covered"] + tech["missing"]) // 2):
        well.append("You covered several of the key concepts: " + ", ".join(tech["covered"][:4]) + ".")
    if star.get("applicable"):
        for k, v in star["components"].items():
            if v["strength"] >= 1:
                well.append(f"Clear {k.title()} component.")
            else:
                missing.append(f"{k.title()}: {v['improve']}")
        if star.get("ownership_note"):
            weak.append(star["ownership_note"])
    if tech and tech["missing"]:
        missing.append("Concepts not mentioned: " + ", ".join(tech["missing"][:5]) + ".")
    if wc < 30:
        weak.append(f"The answer is very short ({wc} words). Aim for roughly 60-150 words.")
        impr.append("Add one concrete example and explain your reasoning.")
    if scores["specificity"] < 5:
        weak.append("Many statements are general. Replace words like 'things' or 'good' with specifics.")
        impr.append("Name the tool, the number, the person or the decision involved.")
    if scores["evidence"] < 5:
        weak.append("There is little evidence behind your claims.")
        impr.append("Add a short real example and the outcome it produced.")
    if lang["filler_rate"] > 0.04:
        weak.append("Frequent filler words: " + ", ".join(f"{k} ×{v}" for k, v in lang["fillers"][:4]) + ".")
        impr.append("Pause silently instead of using a filler. A short pause sounds more confident.")
    if lang["hedge_rate"] > 0.05:
        weak.append("Hedging (" + ", ".join(k for k, _ in lang["hedges"][:4]) + ") makes correct points sound unsure.")
        impr.append("State what you know directly. Say what you'd check instead of 'I guess'.")
    if q.get("category") == "behavioral":
        scaffold = ("Situation: \"At [where/when], [context]...\"  Task: \"My responsibility was to [goal]...\"  "
                    "Action: \"I [step 1], then [step 2], and [step 3]...\"  Result: \"As a result, [metric/outcome], "
                    "and I learned [lesson].\"")
    elif q.get("category") == "technical":
        scaffold = ("Definition in one sentence -> how it works -> a small example -> a trade-off or when you'd "
                    "use it -> one common pitfall.")
    else:
        scaffold = ("Direct answer in one sentence -> two reasons with a real example for each -> "
                    "link back to the role.")
    tips.append("Lead with the direct answer in your first sentence, then support it.")
    if q.get("category") == "behavioral":
        tips.append("Prepare 4-5 stories you can adapt to different behavioral questions.")
    if q.get("category") == "technical":
        tips.append("Think aloud: define the concept, give an example, then mention a trade-off.")
    return {"did_well": well or ["You attempted the question. Use the suggestions below to strengthen it."],
            "missing": missing, "weak_points": weak, "improvements": impr or ["Keep adding specifics and outcomes."],
            "stronger_example": scaffold,
            "stronger_example_label": "Answer scaffold. Rule-based mode cannot write a tailored model answer; "
                                      "connect an LLM for that.",
            "next_tips": tips}


def _rule_follow_up(q, answer, scores, star, tech, wc) -> dict:
    cat = q.get("category")
    if wc < 25:
        text = {"behavioral": "Could you give me one specific example, including what you personally did?",
                "technical": "Could you go into more depth, perhaps with a small example?"}.get(
            cat, "Could you expand on that a little, with a concrete example?")
        return {"needed": True, "type": "clarification", "question": text, "source": "template"}
    if star.get("applicable"):
        for k, text in (("result", "What was the outcome, and how did you measure it?"),
                        ("action", "What exactly did you do yourself, step by step?"),
                        ("task", "What was your specific responsibility in that situation?")):
            if star["components"][k]["strength"] < 1:
                return {"needed": True, "type": "followup", "question": text, "source": "template"}
    if tech and tech.get("missing") and scores["technical"] is not None and scores["technical"] < 7:
        return {"needed": True, "type": "followup", "source": "template",
                "question": f"How would {tech['missing'][0]} come into play here?"}
    if scores["evidence"] < 5:
        return {"needed": True, "type": "followup", "question": "Can you give a real example where you saw this in practice?",
                "source": "template"}
    return {"needed": False, "type": "followup", "question": "", "source": "template"}
