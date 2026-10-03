"""v1.1 observability: request ids, one JSON log line per request, and Prometheus metrics at /metrics.

What is logged: time, level, request id, method, route, status, duration. Never a request body, a customer id, a
feature value or an API key. Metrics are kept in memory by hand (a few counters and one histogram): no extra
dependency, and the text format is the Prometheus exposition format 0.0.4.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from collections import defaultdict

REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
LOG_FIELDS = ("request_id", "method", "route", "status", "duration_ms", "model_version", "reason")


def request_id_from(header: str | None) -> str:
    """Keep a caller's id if it is a safe token (so logs can be joined across services), else make one."""
    if header and REQUEST_ID.match(header):
        return header
    return uuid.uuid4().hex


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in LOG_FIELDS:
            if hasattr(record, key):
                line[key] = getattr(record, key)
        return json.dumps(line)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers[:] = []
        logging.getLogger(name).propagate = True


def escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class Metrics:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.requests: dict[tuple[str, str, str], int] = defaultdict(int)
        self.buckets: dict[str, list[int]] = defaultdict(lambda: [0] * len(BUCKETS))
        self.duration_sum: dict[str, float] = defaultdict(float)
        self.duration_count: dict[str, int] = defaultdict(int)
        self.predictions = 0
        self.fallbacks: dict[str, int] = defaultdict(int)

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        with self.lock:
            self.requests[(method, route, str(status))] += 1
            counts = self.buckets[route]
            for i, bound in enumerate(BUCKETS):
                if seconds <= bound:
                    counts[i] += 1
            self.duration_sum[route] += seconds
            self.duration_count[route] += 1

    def predicted(self, n: int) -> None:
        with self.lock:
            self.predictions += n

    def fell_back(self, reason: str) -> None:
        with self.lock:
            self.fallbacks[reason.split(":")[0][:40]] += 1

    def render(self, model_info: dict[str, str]) -> str:
        with self.lock:
            out = [
                "# HELP churncast_model_info The model being served (value is always 1).",
                "# TYPE churncast_model_info gauge",
                "churncast_model_info{" + ",".join(f'{k}="{escape(v)}"' for k, v in model_info.items()) + "} 1",
                "# HELP churncast_requests_total HTTP requests by method, route and status.",
                "# TYPE churncast_requests_total counter",
            ]
            for (method, route, status), n in sorted(self.requests.items()):
                out.append(
                    f'churncast_requests_total{{method="{method}",route="{escape(route)}",status="{status}"}} {n}'
                )
            out += [
                "# HELP churncast_request_duration_seconds Request duration by route.",
                "# TYPE churncast_request_duration_seconds histogram",
            ]
            for route in sorted(self.buckets):
                r = escape(route)
                for bound, n in zip(BUCKETS, self.buckets[route], strict=True):
                    out.append(f'churncast_request_duration_seconds_bucket{{route="{r}",le="{bound}"}} {n}')
                total = self.duration_count[route]
                out.append(f'churncast_request_duration_seconds_bucket{{route="{r}",le="+Inf"}} {total}')
                out.append(f'churncast_request_duration_seconds_sum{{route="{r}"}} {self.duration_sum[route]:.6f}')
                out.append(f'churncast_request_duration_seconds_count{{route="{r}"}} {total}')
            out += [
                "# HELP churncast_predictions_total Customers scored by /v1/predict and /v1/explain.",
                "# TYPE churncast_predictions_total counter",
                f"churncast_predictions_total {self.predictions}",
                "# HELP churncast_explainer_fallbacks_total AI explanations replaced by the template, by reason.",
                "# TYPE churncast_explainer_fallbacks_total counter",
            ]
            for reason, n in sorted(self.fallbacks.items()):
                out.append(f'churncast_explainer_fallbacks_total{{reason="{escape(reason)}"}} {n}')
        return "\n".join(out) + "\n"
