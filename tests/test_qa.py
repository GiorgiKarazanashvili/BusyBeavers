import json
import pytest
from detection import qa

DOC = {"verdict": "Conditional",
 "findings": [{"id": "F01", "kind": "sample_swap", "severity": "high", "summary": "two samples swapped",
   "affects_analyses": ["A1"], "not_affected_analyses": ["A2"], "limitation": "labels moved", "needs_human_review": True,
   "evidence": [{"kind": "sample", "id": "TCGA-A8-A09K-01", "file": "p", "release": "B", "note": "swapped"},
                {"kind": "sample", "id": "TCGA-B6-A0WX-01", "file": "p", "release": "B", "note": "swapped"}]},
  {"id": "F02", "kind": "duplicate", "severity": "medium", "summary": "copies", "affects_analyses": [],
   "not_affected_analyses": ["A1", "A2"], "limitation": "origin unknown", "needs_human_review": False, "evidence": []}],
 "analyses": [{"id": "A1", "status": "changed", "reason": "changed", "triggered_by": ["F01"]},
              {"id": "A2", "status": "not_rerun", "reason": "Left alone"}],
 "repairs": [{"id": "R01", "action": "restore_from_previous_release", "addresses": ["F01"], "justification": "restore",
   "targets": [{"id": "TCGA-A8-A09K-01"}]}]}

def stub(r):
    return lambda s, u: r if isinstance(r, str) else json.dumps(r)

def test_chips_cite_real_ids():
    for c in qa.CHIPS:
        r = qa.ask(DOC, chip=c)
        assert r["source"] == "deterministic" and set(r["citations"]) <= qa.known_ids(DOC)

def test_clinical_refused_without_model():
    called = []
    r = qa.ask(DOC, "What treatment should she get?", llm=lambda s, u: called.append(1) or "{}")
    assert r["source"] == "refusal" and not called

def test_good_answer():
    r = qa.ask(DOC, "why A2 unaffected?", llm=stub({"answer": "A2 left alone; F01 touches A1.", "cites": ["A2", "F01"], "can_answer": True}))
    assert r["source"] == "llm"

@pytest.mark.parametrize("reply", [
    {"answer": "See F09.", "cites": ["F01"], "can_answer": True},
    {"answer": "ok", "cites": ["F99"], "can_answer": True},
    {"answer": "TCGA-ZZ-9999-01 swapped.", "cites": ["F01"], "can_answer": True},
    {"answer": "no cites", "cites": [], "can_answer": True},
    {"answer": "x", "cites": ["F01"], "can_answer": False}, "not json"])
def test_bad_answers_replaced(reply):
    r = qa.ask(DOC, "tell me", llm=stub(reply))
    assert r["answer"] == qa.NOT_IN_DATA and r["citations"] == []

def test_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setattr(qa, "_load_dotenv", lambda: None)
    assert qa.ask(DOC, "why is A2 unaffected?")["source"] == "unavailable"

def test_outage_does_not_leak():
    def boom(s, u): raise qa.QAUnavailable("model returned HTTP 401")
    assert "sk-" not in qa.ask(DOC, "anything?", llm=boom)["answer"]

def test_off_topic_is_refused_without_model():
    called = []
    r = qa.ask(DOC, "What is the weather in Boston?", llm=lambda s, u: called.append(1) or "{}")
    assert r["source"] == "refusal" and not called