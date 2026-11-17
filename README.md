# InterviewIQ: AI-Powered Conversational Interview Preparation Coach

Adaptive mock interviews with follow-up questions generated from the candidate's actual answers, a six-dimension
scoring rubric, structured feedback, human-vs-AI validation and progress analytics.
Stack: Streamlit · Python · SQLite · Plotly · NLTK · optional LLM (Anthropic or any OpenAI-compatible API).

## Quick start (any laptop, no GPU, no paid service required)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # optional: add an API key
streamlit run app.py
```

* **Without an API key** the app runs in **rule-based mode**. Every score, badge, report and PDF says so.
* **With a key** (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`) questions, follow-ups, evaluations and improvement plans are
  produced by the LLM. Any OpenAI-compatible endpoint works through `OPENAI_BASE_URL` (Groq, Gemini's compatible endpoint,
  a local Ollama server...). Check your provider's current free tier and model names. Cost per 5-question interview is a
  few cents with a small model such as `claude-haiku-5-5` or `gpt-4o-mini`.
* Landing page → **Watch a demo** runs a sample interview through the real evaluator (the *candidate answers* are sample
  text written for the demo and are labelled as such; the scores are genuine engine output).
* Evaluator accounts need the `MENTOR_ACCESS_CODE` from `.env` (default `change-me`: change it).
* Tests: `python -m pytest tests -q` (unit tests + headless render of every page).
* API setup: copy `.env.example` to `.env`, add a provider key, then restart Streamlit. See `API_AND_DESIGN_SETUP.md` for Gemini, OpenAI and Groq examples.

## Honesty rules built into the design

| Rule | How it is enforced |
|---|---|
| Rule-based results never pass as LLM results | `ai_evaluations.eval_mode` is `llm` or `rule_based`; every UI card, report and PDF shows the badge; fallback reason is stored |
| LLM failure degrades visibly | Network/JSON errors → rule-based result with `fallback_reason`; never silent |
| Overall score is not model-invented | Computed in code from dimension scores and rubric weights; N/A dimensions are re-normalised |
| No fake human ratings | `human_evaluations` is written only from the evaluator form. Validation shows an empty state until real ratings exist |
| Blind rating | Evaluators don't see the AI's scores until they save their own |
| Engines validated separately | The agreement tab filters by engine, because they are different instruments |
| Demo data kept apart | Demo sessions are excluded from analytics (toggle) and from human review/validation |
| Rule-based technical scoring is limited | Reported as *concept coverage* and states it cannot detect wrong statements; only the LLM mode checks correctness |

## Rubric

| Dimension | Weight | Applies to |
|---|---|---|
| Relevance | 25 | all |
| STAR structure | 15 | behavioral questions |
| Specificity & clarity | 20 | all |
| Evidence & examples | 15 | all |
| Technical correctness | 15 | technical questions |
| Filler & hedging | 10 | all |

Each dimension is 0-10 with written anchors (see Settings → rubric). `overall = Σ(w·s/10) / Σw × 100` over applicable dimensions.
Filler detection is context-aware: code is masked; SQL `LIKE`, "kind of index" and "just-in-time" are protected;
"like" counts only as a discourse marker; about 2% filler and 3% hedging cost nothing, so natural speech is not penalised.

## Architecture

```
app.py                    router, sidebar, session state
core/config.py            env + constants        core/rubric.py      rubric, weights, anchors, overall score
core/llm.py               provider abstraction   core/evaluator.py   LLM engine + rule-based engine
core/interviewer.py       question generation, adaptive difficulty    core/question_bank.py  offline bank
core/service.py           interview flow (answer → evaluate → follow-up / next / finish)
core/nlp.py               filler/hedge/STAR/keyword utilities         core/report.py  final report + plan
core/validation.py        MAE, bias, Pearson, Spearman                core/analytics.py  Plotly charts
core/pdf.py               PDF export             core/demo.py        demo mode      core/db.py  SQLite layer
ui/theme.py               CSS design system, icons, components        ui/pages_*.py  the 11 pages
```

**Conversation logic.** After each answer the evaluator also decides whether a follow-up is worthwhile (probe a vague claim,
a missing result, a technical point) or a clarification is needed (answer too thin). One follow-up per main question.
Next main question difficulty moves up/down from the mean of the last two thread scores (≥75 up, ≤45 down).

**Database (SQLite, 8 tables):** `users`, `candidate_profiles`, `interview_sessions`, `questions` (main/followup/clarification, parent link),
`answers`, `ai_evaluations` (per-dimension columns + JSON details), `human_evaluations` (unique per answer×evaluator), `performance_history`.
Passwords: salted PBKDF2-HMAC-SHA256 (240k iterations).

## Suggested validation protocol (for your report)

1. Collect ≥30 real candidate answers across types (ask classmates to use the app with an LLM key).
2. Ask ≥2 mentors to rate them blind through the evaluator page.
3. Report MAE (overall and per dimension), bias, Pearson r and Spearman ρ from **Agreement analysis**; export the CSV.
4. Repeat for rule-based mode and compare. This is a useful result: it quantifies what the LLM adds.

## Known limitations (say these in your viva)

* Rule-based relevance is vocabulary overlap, not understanding; it cannot detect factually wrong answers.
* LLM scores can vary between runs; validation against humans is how you measure that.
* Text-only answers: no speech analysis, so "filler words" are those typed. Mic input is a natural extension.
* Streamlit has no push timers: the room timer is client-side, and the limit is enforced when you submit.
* Single-process SQLite is right for a demo; use PostgreSQL for multi-user deployment.
