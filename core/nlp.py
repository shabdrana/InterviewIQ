"""Lightweight NLP utilities: tokenising, filler/hedge detection, STAR cue detection.
No NLTK corpora downloads are needed (only the Porter stemmer, which is pure code)."""
from __future__ import annotations

import re

try:
    from nltk.stem import PorterStemmer
    _stem = PorterStemmer().stem
except Exception:  # pragma: no cover
    def _stem(w: str) -> str:
        return w

STOP = set("""a an the and or but if then so of to in on at by for with from as is are was were be been being am do does
did have has had i me my we our you your it its this that these those there here what which who whom how why when where
can could should would will shall may might must not no yes than too very just also about into over under again more most
some any each other such own same""".split())
GENERIC_Q = set("tell describe explain talk walk through time example give difference different mean means work role "
                "please question answer us".split())
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9+#_]*(?:'[a-z]+)?")


def tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def word_count(text: str) -> int:
    return len(text.split())


def stems(text: str, drop_generic: bool = False) -> set[str]:
    out = set()
    for w in tokens(text):
        if w in STOP or len(w) < 3 or (drop_generic and w in GENERIC_Q):
            continue
        out.add(_stem(w))
    return out


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def keyword_hits(answer: str, keywords: list[str]) -> tuple[list[str], list[str]]:
    """A keyword counts as covered when it appears verbatim (case-insensitive, whole token) or when
    all of its stems occur in the answer (so 'filters' matches 'filter')."""
    a, low = stems(answer), answer.lower()
    hit, miss = [], []
    for k in keywords:
        kl = k.lower()
        verbatim = re.search(r"(?<![a-z0-9])" + re.escape(kl) + r"(?![a-z0-9])", low)
        ks = stems(k)
        (hit if verbatim or (ks and ks <= a) else miss).append(k)
    return hit, miss


# --------------------------------------------------------------------- filler / hedging
def _mask_code(text: str) -> str:
    """Blank out code (same length so offsets stay valid): technical text is never 'filler'."""
    return re.sub(r"```.*?```|`[^`]*`", lambda m: " " * len(m.group()), text, flags=re.S)


_FILLERS = [
    ("um / uh", r"\b(?:um+|uh+|uhm+|erm|er|ah+|hmm+)\b"),
    ("you know", r"(?<!do )(?<!did )(?<!would )\byou know\b(?!\s+(?:that|how|what|where|which|why|about)\b)"),
    ("I mean", r"\bi mean\b"),
    ("basically", r"\bbasically\b"),
    ("actually", r"\bactually\b"),
    ("literally", r"\bliterally\b"),
    ("honestly", r"\bhonestly\b"),
    ("obviously", r"\bobviously\b"),
    ("so yeah", r"\bso yeah\b|\band yeah\b"),
    ("stuff like that", r"\b(?:and )?(?:stuff|things) like that\b|\band all that\b|\band so on and so forth\b"),
    ("..., right?", r",\s*right\?"),
]
_HEDGES_STRONG = [r"not (?:really )?sure", r"i guess", r"i (?:do not|don't|dont) know", r"kind of", r"sort of", r"kinda",
                  r"sorta", r"i suppose", r"if i remember correctly", r"something like that", r"or something",
                  r"i'm not certain"]
_HEDGES_SOFT = [r"i think", r"i believe", r"maybe", r"perhaps", r"probably", r"might", r"i feel like", r"somewhat",
                r"possibly", r"i hope"]
# 'kind of' / 'sort of' followed by these nouns is ordinary technical English ("what kind of index"), not hedging.
_TECH_NOUNS = r"(?:data|algorithm|sorting|join|index|query|error|exception|memory|tree|graph|model|problem|input|key|" \
              r"structure|testing|test|loss|learning|database|cache|lock|thread|variable|function|object|class)"


def _like_spans(masked: str) -> list[tuple[int, int]]:
    """'like' as discourse marker only. Comparison/verb use ("like Java", "is like a stack") and
    SQL's LIKE (upper-case) are not flagged."""
    spans = []
    for m in re.finditer(r"\blike\b", masked):
        pre = masked[max(0, m.start() - 12):m.start()].lower()
        post = masked[m.end():m.end() + 14].lower()
        comma_adjacent = pre.rstrip().endswith(",") or post.lstrip().startswith(",")
        be_pronoun = re.search(r"\b(?:was|were|is|am|it's|i'm|and|so|but)\s+$", pre) and \
            re.match(r"\s*(?:i|we|they|he|she|it|really|totally|super|very)\b", post)
        if comma_adjacent or be_pronoun:
            spans.append((m.start(), m.end()))
    return spans


def analyze_language(text: str) -> dict:
    wc = max(1, word_count(text))
    masked = _mask_code(text)
    low = masked.lower()
    filler_spans, counts = [], {}
    for label, pat in _FILLERS:
        for m in re.finditer(pat, low):
            filler_spans.append((m.start(), m.end(), "filler"))
            counts[label] = counts.get(label, 0) + 1
    for s, e in _like_spans(masked):
        filler_spans.append((s, e, "filler"))
        counts["like (as filler)"] = counts.get("like (as filler)", 0) + 1

    hedge_spans, hedge_counts, weighted = [], {}, 0.0
    for weight, group in ((1.0, _HEDGES_STRONG), (0.5, _HEDGES_SOFT)):
        for pat in group:
            for m in re.finditer(rf"\b{pat}\b", low):
                if pat in ("kind of", "sort of") and re.match(rf"\s+{_TECH_NOUNS}\b", low[m.end():m.end() + 20]):
                    continue
                if any(s <= m.start() < e for s, e, _ in filler_spans):
                    continue
                hedge_spans.append((m.start(), m.end(), "hedge"))
                key = text[m.start():m.end()].lower()
                hedge_counts[key] = hedge_counts.get(key, 0) + 1
                weighted += weight

    protected = sorted(set(re.findall(r"\bLIKE\b", masked)) | set(re.findall(r"(?i)\bjust[- ]in[- ]time\b", masked)))
    n_fill = sum(counts.values())
    spans = sorted(filler_spans + hedge_spans)
    return {
        "word_count": word_count(text),
        "filler_count": n_fill, "filler_rate": round(n_fill / wc, 4),
        "hedge_weighted": round(weighted, 1), "hedge_rate": round(weighted / wc, 4),
        "fillers": sorted(counts.items(), key=lambda kv: -kv[1]),
        "hedges": sorted(hedge_counts.items(), key=lambda kv: -kv[1]),
        "protected_terms": protected,
        "spans": [[s, e, t] for s, e, t in spans],
    }


def fluency_score(lang: dict) -> float:
    """Natural speech is tolerated: ~2% filler and ~3% hedging cost nothing."""
    f = max(0.0, lang["filler_rate"] - 0.02) * 100 * 0.7
    h = max(0.0, lang["hedge_rate"] - 0.03) * 100 * 0.5
    return round(max(1.0, min(10.0, 10.0 - f - h)), 1)


def highlight_html(text: str, spans: list) -> str:
    """HTML-escaped text with filler/hedge spans wrapped in <mark>."""
    from html import escape
    out, pos = [], 0
    for s, e, t in sorted(spans):
        if s < pos:
            continue
        out.append(escape(text[pos:s]))
        out.append(f'<mark class="mk-{t}">{escape(text[s:e])}</mark>')
        pos = e
    out.append(escape(text[pos:]))
    return "".join(out).replace("\n", "<br>")


# --------------------------------------------------------------------- STAR
_STAR_CUES = {
    "situation": [r"\bwhen i was\b", r"\bwhile (?:i|we)\b", r"\bduring (?:my|our|the|a)\b",
                  r"\bat (?:my|the|a) (?:internship|company|college|university|school|job|startup|hackathon)\b",
                  r"\bin (?:my|our) (?:project|team|class|final year|internship|first|second|third)\b",
                  r"\blast (?:year|semester|summer|month)\b", r"\bthere was a\b", r"\bour team (?:was|had)\b",
                  r"\bwe were (?:working|building|facing|asked)\b"],
    "task": [r"\bmy (?:role|responsibility|task|goal|job)\b", r"\bi was (?:responsible|assigned|tasked|asked|expected)\b",
             r"\bneeded to\b", r"\bhad to\b", r"\bthe (?:goal|objective|challenge|problem|deadline) was\b",
             r"\btasked with\b", r"\bwe (?:needed|had) to\b", r"\bmy job\b"],
    "action": [r"\bi (?:decided|implemented|built|created|designed|developed|wrote|organi[sz]ed|led|analy[sz]ed|proposed|"
               r"started|set up|collaborated|coordinated|automated|refactored|debugged|tested|reached out|took|made|"
               r"divided|researched|prioriti[sz]ed|negotiated|presented|introduced|split|scheduled|asked)\b"],
    "result": [r"\bas a result\b", r"\bresult(?:ed|ing)?\b", r"\boutcome\b", r"\bin the end\b", r"\bultimately\b",
               r"\bachieved\b", r"\bimproved\b", r"\breduced\b", r"\bincreased\b", r"\bsaved\b", r"\bdelivered\b",
               r"\bwe (?:won|launched|shipped|finished|completed)\b", r"\blearn(?:ed|t)\b", r"\blesson\b",
               r"\b\d+(?:\.\d+)?\s?(?:%|percent|x)\b"],
}
_STAR_ADVICE = {
    "situation": "Open with one or two sentences of context: where, when, and what was going on.",
    "task": "State your specific responsibility or goal, and what made it challenging.",
    "action": "Describe the steps *you* personally took, in order. Use \"I\" and name tools or methods.",
    "result": "Close with the outcome. Quantify it (%, time saved, users, grade) and say what you learned.",
}


def star_heuristic(text: str) -> dict:
    low = text.lower()
    comps = {}
    for k, pats in _STAR_CUES.items():
        found = [m.group(0) for p in pats for m in re.finditer(p, low)]
        n = len(set(found)) if k != "action" else len(found)
        if k == "result" and re.search(r"\d", low):
            n += 1
        strength = 0.0 if n == 0 else (0.5 if n == 1 else 1.0)
        comps[k] = {"strength": strength,
                    "evidence": ", ".join(sorted(set(found))[:3]) if found else "",
                    "improve": "" if strength == 1.0 else _STAR_ADVICE[k]}
    i_ct = len(re.findall(r"\bi\b", low))
    we_ct = len(re.findall(r"\bwe\b|\bour\b", low))
    note = ""
    if we_ct >= 3 and we_ct > 2 * max(1, i_ct):
        note = "You mostly say \"we\". Interviewers want to hear what *you* did."
    return {"applicable": True, "components": comps, "ownership_note": note}


def star_score(star: dict) -> float:
    w = {"situation": 2, "task": 2, "action": 3.5, "result": 2.5}
    return round(sum(w[k] * star["components"][k]["strength"] for k in w), 1)
