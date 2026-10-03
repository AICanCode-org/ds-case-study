"""The AI explainer: a short plain-language note on why one customer's churn risk is high or low.

Safe by design:
- optional: AI_PROVIDER=offline (the default) never calls a model; the deterministic template is used;
- the model only sees numbered facts built from the score and the top contributions (R1, R2, ...): never the
  customer id, never raw records, never a protected attribute (age band is not a model feature);
- OpenAI-compatible HTTP API (Ollama, LM Studio, vLLM, any hosted provider); no SDK, no paid key needed;
- every answer passes the guardrails below or is replaced by the template (fallback=true + reason).

Guardrails (validate):
  1. plain text, at most MAX_CHARS characters, at least 2 fact citations, every citation exists;
  2. every number is a correct rounding of a value in the facts (no invented numbers);
  3. no certainty claims ("will churn", "guaranteed", ...): it is a probability, not a verdict;
  4. no sensitive attributes (age, gender, religion, caste, ...): the note is about behaviour and service.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field

from .model import Model

MAX_CHARS = 600
TOP_REASONS = 3
BANNED = [
    "will churn",
    "will cancel",
    "will leave",
    "will stay",
    "guarantee",
    "guaranteed",
    "certainly",
    "definitely",
    "surely",
    "100%",
]
SENSITIVE = ["age", "aged", "old", "young", "gender", "male", "female", "religion", "caste", "ethnicity", "income"]
CITATION = re.compile(r"\[R(\d+)\]")
NUMBER = re.compile(r"(?<![\w.])[-+−]?\d[\d,]*(?:\.\d+)?")
SYSTEM_PROMPT = (
    "You explain a churn-risk score to a customer-retention agent in 2-3 short sentences. Use ONLY the numbered "
    "facts you are given and cite each fact you use as [R1], [R2]. Never introduce a number that is not in the "
    "facts. It is a probability, not a certainty: never say the customer will churn or stay. Do not mention age, "
    "gender or any personal attribute. Plain text only, no markdown, at most "
    f"{MAX_CHARS} characters."
)


@dataclass(frozen=True)
class Fact:
    id: str
    text: str
    values: tuple[float, ...]


@dataclass
class Explanation:
    text: str
    source: str  # "template" or "llm"
    fallback: bool
    reason: str | None
    model: str | None
    facts: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Settings:
    provider: str = "offline"
    base_url: str = "http://localhost:11434/v1"
    model: str = "llama3.2"
    api_key: str = field(default="", repr=False)  # never printed or logged
    timeout_ms: int = 4000

    @classmethod
    def from_env(cls, env: dict | None = None) -> Settings:
        env = os.environ if env is None else env
        provider = env.get("AI_PROVIDER", "offline").strip().lower() or "offline"
        if provider not in ("offline", "llm"):
            provider = "offline"
        try:
            timeout = max(100, min(30_000, int(env.get("LLM_TIMEOUT_MS", "4000"))))
        except ValueError:
            timeout = 4000
        return cls(
            provider=provider,
            base_url=env.get("LLM_BASE_URL", cls.base_url).rstrip("/"),
            model=env.get("LLM_MODEL", cls.model),
            api_key=env.get("LLM_API_KEY", ""),
            timeout_ms=timeout,
        )


def shown(value: float, unit: str) -> str:
    """A feature value as the note shows it."""
    if unit == "share":
        return f"{round(100 * value, 1):g} %"
    if unit == "flag":
        return "yes" if value >= 0.5 else "no"
    return f"{round(value, 1):g} {unit}"


def typical(mean: float, unit: str) -> str:
    if unit == "flag":
        return f"true for {round(100 * mean):g} % of subscribers"
    return f"typical: {shown(mean, unit)}"


def fact(fact_id: str, text: str) -> Fact:
    """A fact and the numbers it contains: the only numbers an answer may use."""
    return Fact(fact_id, text, tuple(float(n.replace(",", "")) for n in NUMBER.findall(text)))


def build_facts(model: Model, row: dict) -> list[Fact]:
    p = model.score(row)
    base = model.artefact["base_rate"]
    band = model.risk_band(p)
    facts = [
        fact(
            "R1",
            f"Predicted chance of not renewing next month: {round(100 * p, 1):g} % ({band} risk); "
            f"the average subscriber: {round(100 * base, 1):g} %.",
        )
    ]
    for i, c in enumerate(model.contributions(row)[:TOP_REASONS], start=2):
        spec = model.specs[c["feature"]]
        direction = "raises" if c["contribution"] > 0 else "lowers"
        text = (
            f"{spec.display[0].upper()}{spec.display[1:]}: {shown(c['value'], spec.unit)} "
            f"({typical(c['mean'], spec.unit)}); this {direction} the risk."
        )
        facts.append(fact(f"R{i}", text))
    return facts


def facts_block(facts: list[Fact]) -> str:
    return "\n".join(f"[{f.id}] {f.text}" for f in facts)


def template_text(facts: list[Fact], band: str) -> str:
    """The deterministic note: same input, same text, always passes validate()."""
    reasons = " ".join(f"{f.text} [{f.id}]" for f in facts[1:])
    action = (
        "Worth a retention call this month." if band == "high" else "No call needed now; keep an eye on the next month."
    )
    return f"{facts[0].text} [R1] {reasons} {action}"


def sanitise(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", text)
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"[*_`#>|]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def allowed(token: str, values: list[float]) -> bool:
    clean = token.replace(",", "").replace("−", "-").lstrip("+-")
    try:
        number = float(clean)
    except ValueError:
        return False
    decimals = len(clean.split(".")[1]) if "." in clean else 0
    tolerance = 0.5 * 10 ** (-decimals) + 1e-9
    return any(abs(number - abs(v)) <= tolerance for v in values)


def validate(text: str, facts: list[Fact]) -> str | None:
    """None when the text passes every guardrail, else the reason it fails."""
    if not text:
        return "empty answer"
    if len(text) > MAX_CHARS:
        return f"too long ({len(text)} > {MAX_CHARS} characters)"
    cited = [int(n) for n in CITATION.findall(text)]
    if len(set(cited)) < 2:
        return "fewer than 2 fact citations"
    if any(n < 1 or n > len(facts) for n in cited):
        return "cites a fact that does not exist"
    lower = text.lower()
    for word in BANNED:
        if word in lower:
            return f"certainty claim: {word!r}"
    for word in SENSITIVE:
        if re.search(rf"\b{re.escape(word)}\b", lower):
            return f"sensitive attribute: {word!r}"
    values = [v for f in facts for v in f.values]
    for token in NUMBER.findall(CITATION.sub(" ", text)):
        if not allowed(token, values):
            return f"number not in the facts: {token}"
    return None


def call_llm(settings: Settings, facts: list[Fact]) -> str:
    body = json.dumps(
        {
            "model": settings.model,
            "temperature": 0,
            "max_tokens": 250,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Facts:\n" + facts_block(facts)},
            ],
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key}"
    req = urllib.request.Request(f"{settings.base_url}/chat/completions", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=settings.timeout_ms / 1000) as resp:
        data = json.loads(resp.read(100_000).decode("utf-8"))
    return str(data["choices"][0]["message"]["content"])


def explain(model: Model, row: dict, settings: Settings | None = None) -> Explanation:
    settings = settings or Settings.from_env()
    facts = build_facts(model, row)
    band = model.risk_band(model.score(row))
    fact_dicts = [{"id": f.id, "text": f.text} for f in facts]

    def template(reason: str | None) -> Explanation:
        return Explanation(template_text(facts, band), "template", reason is not None, reason, None, fact_dicts)

    if settings.provider != "llm":
        return template(None)
    try:
        text = sanitise(call_llm(settings, facts))
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        return template(f"provider unreachable: {type(exc).__name__}")
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        return template(f"unexpected provider response: {type(exc).__name__}")
    problem = validate(text, facts)
    if problem:
        return template(f"guardrail: {problem}")
    return Explanation(text, "llm", False, None, settings.model, fact_dicts)
