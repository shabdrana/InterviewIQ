"""SQLite layer. Plain sqlite3, one short-lived connection per call."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager

from . import config
from .rubric import DIMENSIONS

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  full_name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'candidate',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS candidate_profiles(
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  college TEXT, degree TEXT, grad_year INTEGER, target_role TEXT,
  skills TEXT, bio TEXT, experience_level TEXT DEFAULT 'Fresher',
  prefer_rule_based INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS interview_sessions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  interview_type TEXT, difficulty TEXT, experience_level TEXT, domain TEXT,
  num_questions INTEGER, duration_min INTEGER, instant_feedback INTEGER DEFAULT 1,
  status TEXT DEFAULT 'in_progress', is_demo INTEGER DEFAULT 0,
  started_at TEXT DEFAULT (datetime('now')), ended_at TEXT,
  overall_score REAL, eval_mode TEXT, report_json TEXT
);
CREATE TABLE IF NOT EXISTS questions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  parent_id INTEGER REFERENCES questions(id) ON DELETE CASCADE,
  kind TEXT DEFAULT 'main',            -- main | followup | clarification
  text TEXT NOT NULL, transition TEXT, category TEXT, difficulty TEXT,
  source TEXT,                         -- llm | bank | template
  expected_keywords TEXT DEFAULT '[]',
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS answers(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question_id INTEGER UNIQUE NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  text TEXT NOT NULL, word_count INTEGER, seconds_taken INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS ai_evaluations(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  answer_id INTEGER UNIQUE NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
  eval_mode TEXT NOT NULL,             -- 'llm' | 'rule_based'
  provider TEXT, model TEXT, fallback_reason TEXT,
  relevance REAL, star REAL, specificity REAL, evidence REAL, technical REAL, fluency REAL,
  overall REAL NOT NULL, details_json TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS human_evaluations(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  answer_id INTEGER NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
  evaluator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  relevance REAL, star REAL, specificity REAL, evidence REAL, technical REAL, fluency REAL,
  overall REAL NOT NULL, comments TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(answer_id, evaluator_id)
);
CREATE TABLE IF NOT EXISTS performance_history(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_id INTEGER UNIQUE NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
  recorded_at TEXT DEFAULT (datetime('now')),
  interview_type TEXT, domain TEXT, eval_mode TEXT, is_demo INTEGER DEFAULT 0,
  overall REAL, relevance REAL, star REAL, specificity REAL, evidence REAL, technical REAL, fluency REAL
);
CREATE INDEX IF NOT EXISTS idx_q_session ON questions(session_id, seq);
CREATE INDEX IF NOT EXISTS idx_sess_user ON interview_sessions(user_id);
"""


@contextmanager
def conn():
    path = config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init_db() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _one(cur) -> dict | None:
    r = cur.fetchone()
    return dict(r) if r else None


# ---------------------------------------------------------------- users
def create_user(email: str, full_name: str, password_hash: str, role: str = "candidate") -> int:
    with conn() as c:
        cur = c.execute("INSERT INTO users(email, full_name, password_hash, role) VALUES (?,?,?,?)",
                        (email.lower().strip(), full_name.strip(), password_hash, role))
        uid = cur.lastrowid
        if role == "candidate":
            c.execute("INSERT INTO candidate_profiles(user_id) VALUES (?)", (uid,))
        return uid


def get_user_by_email(email: str) -> dict | None:
    with conn() as c:
        return _one(c.execute("SELECT * FROM users WHERE email=?", (email.lower().strip(),)))


def get_user(uid: int) -> dict | None:
    with conn() as c:
        return _one(c.execute("SELECT * FROM users WHERE id=?", (uid,)))


def update_user(uid: int, **fields) -> None:
    allowed = {"full_name", "password_hash"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    with conn() as c:
        c.execute(f"UPDATE users SET {', '.join(k + '=?' for k in fields)} WHERE id=?", (*fields.values(), uid))


def delete_user(uid: int) -> None:
    with conn() as c:
        c.execute("DELETE FROM users WHERE id=?", (uid,))


def get_profile(uid: int) -> dict:
    with conn() as c:
        return _one(c.execute("SELECT * FROM candidate_profiles WHERE user_id=?", (uid,))) or {"user_id": uid}


def save_profile(uid: int, **fields) -> None:
    allowed = {"college", "degree", "grad_year", "target_role", "skills", "bio", "experience_level", "prefer_rule_based"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    with conn() as c:
        c.execute("INSERT OR IGNORE INTO candidate_profiles(user_id) VALUES (?)", (uid,))
        if fields:
            c.execute(f"UPDATE candidate_profiles SET {', '.join(k + '=?' for k in fields)} WHERE user_id=?",
                      (*fields.values(), uid))


# ---------------------------------------------------------------- sessions
def create_session(uid: int, setup: dict, is_demo: bool = False) -> int:
    with conn() as c:
        cur = c.execute(
            """INSERT INTO interview_sessions(user_id, interview_type, difficulty, experience_level, domain,
               num_questions, duration_min, instant_feedback, is_demo) VALUES (?,?,?,?,?,?,?,?,?)""",
            (uid, setup["interview_type"], setup["difficulty"], setup["experience_level"], setup.get("domain"),
             setup["num_questions"], setup["duration_min"], int(setup.get("instant_feedback", True)), int(is_demo)))
        return cur.lastrowid


def get_session(sid: int) -> dict | None:
    with conn() as c:
        return _one(c.execute("SELECT * FROM interview_sessions WHERE id=?", (sid,)))


def update_session(sid: int, **fields) -> None:
    allowed = {"status", "ended_at", "overall_score", "eval_mode", "report_json"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if fields:
        with conn() as c:
            c.execute(f"UPDATE interview_sessions SET {', '.join(k + '=?' for k in fields)} WHERE id=?",
                      (*fields.values(), sid))


def list_sessions(uid: int, include_demo: bool = True) -> list[dict]:
    q = "SELECT * FROM interview_sessions WHERE user_id=?" + ("" if include_demo else " AND is_demo=0")
    with conn() as c:
        return _rows(c.execute(q + " ORDER BY id DESC", (uid,)))


def delete_session(sid: int) -> None:
    with conn() as c:
        c.execute("DELETE FROM interview_sessions WHERE id=?", (sid,))


# ---------------------------------------------------------------- questions / answers
def add_question(sid: int, text: str, *, kind: str = "main", parent_id: int | None = None, category: str = "general",
                 difficulty: str = "Intermediate", source: str = "bank", transition: str = "",
                 expected_keywords: list[str] | None = None) -> int:
    with conn() as c:
        seq = c.execute("SELECT COALESCE(MAX(seq),0)+1 FROM questions WHERE session_id=?", (sid,)).fetchone()[0]
        cur = c.execute(
            """INSERT INTO questions(session_id, seq, parent_id, kind, text, transition, category, difficulty,
               source, expected_keywords) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (sid, seq, parent_id, kind, text, transition, category, difficulty, source,
             json.dumps(expected_keywords or [])))
        return cur.lastrowid


def add_answer(question_id: int, text: str, seconds_taken: int | None = None) -> int:
    wc = len(text.split())
    with conn() as c:
        cur = c.execute("INSERT INTO answers(question_id, text, word_count, seconds_taken) VALUES (?,?,?,?)",
                        (question_id, text.strip(), wc, seconds_taken))
        return cur.lastrowid


def conversation(sid: int) -> list[dict]:
    """Questions in order, each joined with its answer and AI evaluation (if any)."""
    sql = """SELECT q.id AS question_id, q.seq, q.parent_id, q.kind, q.text AS question, q.transition, q.category,
                    q.difficulty, q.source, q.expected_keywords,
                    a.id AS answer_id, a.text AS answer, a.word_count, a.seconds_taken,
                    e.eval_mode, e.provider, e.model, e.fallback_reason, e.overall,
                    e.relevance, e.star, e.specificity, e.evidence, e.technical, e.fluency, e.details_json
             FROM questions q LEFT JOIN answers a ON a.question_id=q.id
             LEFT JOIN ai_evaluations e ON e.answer_id=a.id
             WHERE q.session_id=? ORDER BY q.seq"""
    with conn() as c:
        rows = _rows(c.execute(sql, (sid,)))
    for r in rows:
        r["expected_keywords"] = json.loads(r["expected_keywords"] or "[]")
        r["details"] = json.loads(r["details_json"]) if r.get("details_json") else None
    return rows


def get_question(qid: int) -> dict | None:
    with conn() as c:
        r = _one(c.execute("SELECT * FROM questions WHERE id=?", (qid,)))
    if r:
        r["expected_keywords"] = json.loads(r["expected_keywords"] or "[]")
    return r


# ---------------------------------------------------------------- evaluations
def save_ai_eval(answer_id: int, ev: dict) -> None:
    s = ev["scores"]
    with conn() as c:
        c.execute(
            """INSERT OR REPLACE INTO ai_evaluations(answer_id, eval_mode, provider, model, fallback_reason,
               relevance, star, specificity, evidence, technical, fluency, overall, details_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (answer_id, ev["eval_mode"], ev.get("provider"), ev.get("model"), ev.get("fallback_reason"),
             *[s.get(d) for d in DIMENSIONS], ev["overall"], json.dumps(ev["details"])))


def save_human_eval(answer_id: int, evaluator_id: int, scores: dict, overall: float, comments: str) -> None:
    with conn() as c:
        c.execute(
            """INSERT INTO human_evaluations(answer_id, evaluator_id, relevance, star, specificity, evidence,
               technical, fluency, overall, comments) VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(answer_id, evaluator_id) DO UPDATE SET relevance=excluded.relevance, star=excluded.star,
               specificity=excluded.specificity, evidence=excluded.evidence, technical=excluded.technical,
               fluency=excluded.fluency, overall=excluded.overall, comments=excluded.comments,
               created_at=datetime('now')""",
            (answer_id, evaluator_id, *[scores.get(d) for d in DIMENSIONS], overall, comments))


def get_human_eval(answer_id: int, evaluator_id: int) -> dict | None:
    with conn() as c:
        return _one(c.execute("SELECT * FROM human_evaluations WHERE answer_id=? AND evaluator_id=?",
                              (answer_id, evaluator_id)))


def reviewable_answers(evaluator_id: int) -> list[dict]:
    """Real (non-demo) candidate answers, with whether this evaluator has rated them."""
    sql = """SELECT a.id AS answer_id, a.text AS answer, a.word_count, q.text AS question, q.category, q.kind,
                    s.id AS session_id, s.interview_type, s.domain, s.user_id,
                    e.eval_mode, e.overall AS ai_overall,
                    (SELECT COUNT(*) FROM human_evaluations h WHERE h.answer_id=a.id AND h.evaluator_id=?) AS rated_by_me
             FROM answers a JOIN questions q ON q.id=a.question_id
             JOIN interview_sessions s ON s.id=q.session_id
             JOIN ai_evaluations e ON e.answer_id=a.id
             WHERE s.is_demo=0 ORDER BY a.id DESC"""
    with conn() as c:
        return _rows(c.execute(sql, (evaluator_id,)))


def get_ai_eval(answer_id: int) -> dict | None:
    with conn() as c:
        r = _one(c.execute("SELECT * FROM ai_evaluations WHERE answer_id=?", (answer_id,)))
    if r:
        r["details"] = json.loads(r["details_json"])
    return r


def paired_rows(eval_mode: str | None = None) -> list[dict]:
    """One row per answer rated by >=1 human: mean human score per dimension + AI score."""
    cols_h = ", ".join(f"AVG(h.{d}) AS h_{d}" for d in DIMENSIONS)
    cols_a = ", ".join(f"e.{d} AS a_{d}" for d in DIMENSIONS)
    sql = f"""SELECT a.id AS answer_id, e.eval_mode, e.overall AS a_overall, AVG(h.overall) AS h_overall,
                     COUNT(h.id) AS n_raters, {cols_a}, {cols_h}
              FROM human_evaluations h JOIN answers a ON a.id=h.answer_id
              JOIN ai_evaluations e ON e.answer_id=a.id
              JOIN questions q ON q.id=a.question_id JOIN interview_sessions s ON s.id=q.session_id
              WHERE s.is_demo=0 {"AND e.eval_mode=?" if eval_mode else ""}
              GROUP BY a.id"""
    with conn() as c:
        return _rows(c.execute(sql, (eval_mode,) if eval_mode else ()))


# ---------------------------------------------------------------- performance history
def record_performance(session_id: int, user_id: int, meta: dict, overall: float, dims: dict) -> None:
    with conn() as c:
        c.execute(
            """INSERT OR REPLACE INTO performance_history(user_id, session_id, interview_type, domain, eval_mode,
               is_demo, overall, relevance, star, specificity, evidence, technical, fluency)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, session_id, meta["interview_type"], meta.get("domain"), meta.get("eval_mode"),
             int(meta.get("is_demo", 0)), overall, *[dims.get(d) for d in DIMENSIONS]))


def performance(uid: int, include_demo: bool = False) -> list[dict]:
    q = "SELECT p.*, s.started_at, s.difficulty FROM performance_history p JOIN interview_sessions s ON s.id=p.session_id WHERE p.user_id=?"
    if not include_demo:
        q += " AND p.is_demo=0"
    with conn() as c:
        return _rows(c.execute(q + " ORDER BY s.id", (uid,)))
