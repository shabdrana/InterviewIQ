"""Renders every page headlessly with Streamlit's AppTest to catch runtime errors."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
APP = str(ROOT / "app.py")


from streamlit.testing.v1 import AppTest  # noqa: E402

from core import auth, db, demo  # noqa: E402

db.init_db()
USER = auth.demo_user()
MENTOR = db.get_user(db.create_user("smoke-mentor@x.com", "Mentor One", auth.hash_password("password1"), "mentor"))
SID = demo.run_demo(USER["id"], None)


def _run(user, page, **state):
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["user"] = user
    at.session_state["page"] = page
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_public_pages():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    at.session_state["page"] = "auth"
    at.run()
    assert not at.exception


def test_candidate_pages():
    for page in ("dashboard", "setup", "room", "feedback", "report", "analytics", "history", "settings"):
        _run(USER, page, view_sid=SID)


def test_interview_flow():
    at = _run(USER, "setup")
    next(b for b in at.button if b.key == "su_go").click().run()
    assert not at.exception
    assert at.session_state["page"] == "room"
    sid = at.session_state["active_sid"]
    for _ in range(3):
        ta = at.text_area[0]
        ta.set_value("During my project our team had two weeks. I was responsible for the API, I built it in Flask "
                     "and as a result we shipped 2 days early with 92% on the demo.").run()
        form_btn = [b for b in at.button if b.label == "Submit answer"][0]
        form_btn.click().run()
        assert not at.exception, [e.value for e in at.exception]
        if at.session_state["page"] == "report":
            break
    assert db.get_session(sid)["status"] in ("in_progress", "completed")


def test_mentor_pages():
    _run(MENTOR, "mentor")
    _run(MENTOR, "settings")
