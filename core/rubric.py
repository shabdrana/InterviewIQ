"""The scoring rubric: one definition used by the LLM prompt, the rule-based
fallback, the human evaluator form and the final report."""
from __future__ import annotations

DIMENSIONS = ["relevance", "star", "specificity", "evidence", "technical", "fluency"]

LABELS = {
    "relevance": "Relevance",
    "star": "STAR structure",
    "specificity": "Specificity & clarity",
    "evidence": "Evidence & examples",
    "technical": "Technical correctness",
    "fluency": "Filler & hedging",
}

WEIGHTS = {"relevance": 25, "star": 15, "specificity": 20, "evidence": 15, "technical": 15, "fluency": 10}

DESCRIPTIONS = {
    "relevance": "Does the answer address what was actually asked?",
    "star": "Behavioral answers only: Situation, Task, Action, Result are all present and ordered.",
    "specificity": "Concrete, clear and precise rather than vague or generic.",
    "evidence": "Real examples, numbers, outcomes or artefacts that back up the claims.",
    "technical": "Technical questions only: statements are correct and cover the key concepts.",
    "fluency": "Excessive filler or hedging that weakens the message. Natural conversational style is not penalised.",
}

ANCHORS = {
    "relevance": {"0-2": "Off-topic or ignores the question", "3-4": "Touches the topic but misses the main point",
                  "5-6": "Answers part of the question", "7-8": "Answers the question directly with minor gaps",
                  "9-10": "Fully and directly answers every part"},
    "star": {"0-2": "No recognisable STAR components", "3-4": "One or two components, mostly Action",
             "5-6": "Three components, or all four but thin", "7-8": "All four present, one underdeveloped",
             "9-10": "All four clear, ordered, with a quantified Result and personal ownership"},
    "specificity": {"0-2": "Generic statements only", "3-4": "Mostly generic with a few details",
                    "5-6": "Mix of specific and vague", "7-8": "Mostly specific and clear",
                    "9-10": "Precise, concrete and easy to follow throughout"},
    "evidence": {"0-2": "No example or support", "3-4": "Claims with a passing mention of an example",
                 "5-6": "One example without outcome or detail", "7-8": "Clear example with some outcome/metric",
                 "9-10": "Strong, verifiable example(s) with measurable outcomes"},
    "technical": {"0-2": "Mostly incorrect or no technical content", "3-4": "Significant errors or missing core ideas",
                  "5-6": "Broadly correct but shallow or one notable error", "7-8": "Correct with good coverage",
                  "9-10": "Correct, complete and shows depth (trade-offs, edge cases)"},
    "fluency": {"0-2": "Filler/hedging dominates the answer", "3-4": "Frequent filler or hedging that weakens claims",
                "5-6": "Noticeable but tolerable", "7-8": "Occasional, natural speech patterns",
                "9-10": "Confident and clean; any informal style does not distract"},
}

BANDS = [(85, "Excellent"), (70, "Strong"), (55, "Developing"), (40, "Needs work"), (0, "Foundational")]


def applicable_dimensions(category: str) -> dict[str, bool]:
    """STAR applies to behavioral questions, technical correctness to technical ones."""
    return {d: not ((d == "star" and category != "behavioral") or (d == "technical" and category != "technical"))
            for d in DIMENSIONS}


def overall_score(scores: dict) -> float:
    """Weighted mean of the dimensions that were scored (None = not applicable),
    re-normalised so that N/A dimensions neither help nor hurt. Result is 0-100."""
    num = den = 0.0
    for d in DIMENSIONS:
        s = scores.get(d)
        if s is None:
            continue
        num += WEIGHTS[d] * float(s) / 10.0
        den += WEIGHTS[d]
    return round(100.0 * num / den, 1) if den else 0.0


def band(score: float) -> str:
    return next(name for floor, name in BANDS if score >= floor)


def rubric_text() -> str:
    lines = []
    for d in DIMENSIONS:
        lines.append(f"- {d} (weight {WEIGHTS[d]}): {DESCRIPTIONS[d]}")
        for rng, txt in ANCHORS[d].items():
            lines.append(f"    {rng}: {txt}")
    return "\n".join(lines)
