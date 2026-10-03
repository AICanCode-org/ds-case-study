import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import ClassVar

import pytest

from churncast_api.explainer import MAX_CHARS, Settings, build_facts, explain, sanitise, template_text, validate


def test_settings_default_to_offline_and_clamp():
    assert Settings.from_env({}).provider == "offline"
    s = Settings.from_env({"AI_PROVIDER": "LLM", "LLM_TIMEOUT_MS": "5", "LLM_BASE_URL": "http://x/v1/"})
    assert (s.provider, s.timeout_ms, s.base_url) == ("llm", 100, "http://x/v1")
    assert Settings.from_env({"AI_PROVIDER": "magic", "LLM_TIMEOUT_MS": "soon"}).timeout_ms == 4000
    assert "sk-secret" not in repr(Settings(api_key="sk-secret"))


def test_facts_cite_the_score_and_three_reasons(model, row):
    facts = build_facts(model, row)
    assert [f.id for f in facts] == ["R1", "R2", "R3", "R4"]
    assert "%" in facts[0].text and "average subscriber" in facts[0].text
    assert all(f.values for f in facts)


def test_the_template_always_passes_the_guardrails(model, row):
    for r in (row, {**row, "skip_rate_last_month": 0.0, "tickets_90d": 0, "is_new": 0, "tenure_months": 30}):
        facts = build_facts(model, r)
        band = model.risk_band(model.score(r))
        text = template_text(facts, band)
        assert validate(text, facts) is None, text
        assert len(text) <= MAX_CHARS


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("", "empty answer"),
        ("x" * (MAX_CHARS + 1), "too long"),
        ("Risk is high [R1].", "fewer than 2 fact citations"),
        ("Risk is high [R1] [R9].", "does not exist"),
        ("This customer will churn [R1] [R2].", "certainty claim"),
        ("Risk is guaranteed [R1] [R2].", "certainty claim"),
        ("Young customers like this [R1] [R2].", "sensitive attribute"),
        ("Because of her age [R1] [R2].", "sensitive attribute"),
        ("Risk is 87.5 % [R1] [R2].", "number not in the facts"),
    ],
)
def test_guardrails_reject(model, row, text, reason):
    assert reason in validate(text, build_facts(model, row))


def test_sanitise_strips_markup():
    assert sanitise("**Risk** <b>high</b>\n\n`now`") == "Risk high now"


class FakeLLM(BaseHTTPRequestHandler):
    reply = "ok"
    seen: ClassVar[list] = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeLLM.seen.append((dict(self.headers), body))
        out = json.dumps({"choices": [{"message": {"content": FakeLLM.reply}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_llm():
    server = HTTPServer(("127.0.0.1", 0), FakeLLM)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    FakeLLM.seen = []
    yield f"http://127.0.0.1:{server.server_port}/v1"
    server.shutdown()


def test_a_valid_llm_answer_is_used(model, row, fake_llm):
    facts = build_facts(model, row)
    FakeLLM.reply = f"{facts[1].text} [R2] Overall: {facts[0].text} [R1]"
    note = explain(model, row, Settings(provider="llm", base_url=fake_llm, api_key="sk-test"))
    assert (note.source, note.fallback) == ("llm", False)
    headers, body = FakeLLM.seen[0]
    assert headers["Authorization"] == "Bearer sk-test"
    assert body["temperature"] == 0
    assert "C0" not in json.dumps(body)  # never a customer id


def test_an_invented_number_falls_back_to_the_template(model, row, fake_llm):
    FakeLLM.reply = "Risk is 99.9 % [R1] [R2]"
    note = explain(model, row, Settings(provider="llm", base_url=fake_llm))
    assert (note.source, note.fallback) == ("template", True)
    assert note.reason.startswith("guardrail: number not in the facts")


def test_an_unreachable_provider_falls_back(model, row):
    note = explain(model, row, Settings(provider="llm", base_url="http://127.0.0.1:9/v1", timeout_ms=300))
    assert (note.source, note.fallback) == ("template", True)
    assert note.reason.startswith("provider unreachable")


def test_a_malformed_provider_reply_falls_back(model, row, fake_llm, monkeypatch):
    monkeypatch.setattr("churncast_api.explainer.call_llm", lambda s, f: (_ for _ in ()).throw(KeyError("choices")))
    note = explain(model, row, Settings(provider="llm", base_url=fake_llm))
    assert note.reason == "unexpected provider response: KeyError"
