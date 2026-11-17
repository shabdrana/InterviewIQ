"""PDF export of the final report (reportlab)."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .rubric import DIMENSIONS, LABELS

PURPLE, NAVY, MUTED = colors.HexColor("#6D4AFF"), colors.HexColor("#0B1020"), colors.HexColor("#5B6488")


def report_pdf(candidate: str, session: dict, r: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title="InterviewIQ performance report")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=NAVY, fontSize=22, alignment=0, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=PURPLE, fontSize=13, spaceBefore=12, spaceAfter=4)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=13.5)
    small = ParagraphStyle("s", parent=body, fontSize=8, textColor=MUTED)
    P = lambda t, st=body: Paragraph(escape(str(t)), st)

    mode = {"llm": "AI (LLM) evaluation", "rule_based": "Rule-based evaluation (heuristics, not an LLM)",
            "mixed": "Mixed: some answers LLM-evaluated, some rule-based"}[r["eval_mode"]]
    s = [Paragraph("InterviewIQ performance report", h1),
         P(f"{candidate} · {session['interview_type']} interview"
           + (f" · {session['domain']}" if session.get("domain") else "")
           + f" · {session['difficulty']} · generated {r['generated_at']}", small),
         P(f"Scoring engine: {mode}", small), Spacer(1, 6)]

    t = Table([[Paragraph(f"<font size=26 color='#6D4AFF'><b>{r['overall']:.0f}</b></font><font size=11 color='#5B6488'> / 100</font>", body),
                P(f"{r['band']}. Readiness: {r['readiness']['level']}. {r['readiness']['text']} {r['readiness']['caveat']}")]],
              colWidths=[42 * mm, 130 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD2F0")),
                           ("PADDING", (0, 0), (-1, -1), 8)]))
    s += [t, Paragraph("Dimension scores (0-10)", h2)]
    rows = [["Dimension", "Score"]] + [[LABELS[d], "n/a" if r["dimensions"][d] is None else f"{r['dimensions'][d]:.1f}"] for d in DIMENSIONS]
    tt = Table(rows, colWidths=[110 * mm, 30 * mm])
    tt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), PURPLE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD2F0")), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    s.append(tt)

    for title, items in (("Strongest answers", r["strongest"]), ("Weakest answers", r["weakest"])):
        s.append(Paragraph(title, h2))
        for it in items:
            s += [P(f"{it['score']:.0f}/100 · {it['question']}"), P(it["answer"], small), Spacer(1, 3)]

    c = r["communication"]
    s += [Paragraph("Communication analysis", h2),
          P(f"Average answer length {c['avg_words']:.0f} words; {c['short_answers']} answer(s) under 30 words. "
            f"Filler rate {c['avg_filler_pct']}%, hedging rate {c['avg_hedge_pct']}%."
            + (" Most frequent fillers: " + ", ".join(f"{k} x{v}" for k, v in c["top_fillers"]) + "." if c["top_fillers"] else ""))]
    tc = r["technical"]
    s.append(Paragraph("Technical knowledge", h2))
    s.append(P("No technical questions in this interview." if not tc["n"] else
               f"Average technical score {tc['avg']:.1f}/10 over {tc['n']} answer(s). Strong: {', '.join(tc['strong_concepts']) or 'n/a'}. "
               f"To review: {', '.join(tc['missing_concepts']) or 'none flagged'}."
               + (f" Errors noted: {'; '.join(tc['errors'])}." if tc["errors"] else "")))
    st = r["star"]
    s.append(Paragraph("STAR framework", h2))
    s.append(P("No behavioral questions in this interview." if not st["n"] else
               "Component strength (0-1): " + ", ".join(f"{k.title()} {v:.2f}" for k, v in st["components"].items() if v is not None)
               + f". Weakest component: {(st['weakest'] or 'n/a').title()}."))
    s.append(Paragraph("Personalised improvement plan" + ("" if r["plan_source"] == "llm" else " (rule-based)"), h2))
    for p in r["plan"]:
        s.append(P(p["focus"], ParagraphStyle("pf", parent=body, fontName="Helvetica-Bold")))
        for a in p["actions"]:
            s.append(P("• " + a))
        if p["practice"]:
            s.append(P("Practice: " + p["practice"], small))
    s += [Spacer(1, 10), P("Scores come from the engine named above. They are practice feedback, not a hiring decision. "
                           "Validation against human mentors is reported separately in the app.", small)]
    doc.build(s)
    return buf.getvalue()


def transcript_text(session: dict, conv: list[dict]) -> str:
    lines = [f"InterviewIQ transcript: {session['interview_type']} / {session['difficulty']}", ""]
    for r in conv:
        lines.append(f"INTERVIEWER ({r['kind']}): {r['question']}")
        if r.get("answer"):
            lines.append(f"CANDIDATE: {r['answer']}")
            lines.append(f"[{r['eval_mode']}] overall {r['overall']:.0f}/100")
        lines.append("")
    return "\n".join(lines)
