"""Audit trail for one search: what ran under the hood, in order, with timings.

Each search starts a fresh `AuditLog`. The pipeline adds one `AuditEvent` per
step (Claude calls, supplier searches, ranking, purchase drafts) and the UI shows
`to_text()` in a collapsed panel. Only facts about the work are recorded: model,
timings, token counts, counts and the parsed fields. Prompts and Claude's full
replies are never stored here.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime

# Short tags shown in the text log, padded so the columns line up.
KINDS = {
    "request": "REQUEST",
    "llm": "LLM",
    "supplier": "SUPPLIER",
    "rank": "RANKING",
    "purchase": "PURCHASE",
}
_TAG_WIDTH = max(len(k) for k in KINDS.values())


@dataclass
class AuditEvent:
    kind: str  # a key of KINDS
    title: str
    offset_s: float  # seconds since the search started
    duration_ms: int | None = None
    status: str = "ok"  # ok | warning | error
    details: list[str] = field(default_factory=list)

    def header(self) -> str:
        parts = [self.title]
        if self.duration_ms is not None:
            parts.append(format_duration(self.duration_ms))
        parts.append(self.status.upper())
        return " · ".join(parts)


@dataclass
class AuditLog:
    request_text: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now().replace(microsecond=0))
    events: list[AuditEvent] = field(default_factory=list)
    _t0: float = field(default_factory=time.perf_counter, repr=False)

    def now(self) -> float:
        """A timestamp to pass back as `started` when an event is added later."""
        return time.perf_counter()

    def add(
        self,
        kind: str,
        title: str,
        *details: str,
        status: str = "ok",
        duration_ms: int | None = None,
        started: float | None = None,
    ) -> AuditEvent:
        offset = (started if started is not None else time.perf_counter()) - self._t0
        event = AuditEvent(kind, title, round(offset, 2), duration_ms, status, [d for d in details if d])
        self.events.append(event)
        return event

    @contextmanager
    def step(self, kind: str, title: str) -> Iterator[AuditEvent]:
        """Time a block. Add detail lines to the yielded event; an exception marks it as an error."""
        start = time.perf_counter()
        event = self.add(kind, title, started=start)
        try:
            yield event
        except Exception as exc:
            event.status = "error"
            event.details.append(f"error: {exc}")
            raise
        finally:
            event.duration_ms = elapsed_ms(start)

    def count(self, kind: str) -> int:
        return sum(e.kind == kind for e in self.events)

    @property
    def total_ms(self) -> int:
        """How long the search took. A purchase drafted later is not part of it."""
        ends = [e.offset_s * 1000 + (e.duration_ms or 0) for e in self.events if e.kind != "purchase"]
        return round(max(ends, default=0))

    def summary(self) -> str:
        llm, suppliers = self.count("llm"), self.count("supplier")
        return (
            f"{format_duration(self.total_ms)} · {llm} LLM call{'s' * (llm != 1)} · "
            f"{suppliers} supplier search{'es' * (suppliers != 1)}"
        )

    def to_text(self) -> str:
        lines = [
            f"Audit log · search started {self.started_at:%Y-%m-%d %H:%M:%S}",
            f'Request: "{self.request_text}"',
            "",
        ]
        indent = " " * (10 + _TAG_WIDTH + 2)
        for e in self.events:
            lines.append(f"{'+' + format(e.offset_s, '.2f') + 's':>9} {KINDS[e.kind]:<{_TAG_WIDTH}}  {e.header()}")
            lines += [indent + d for d in e.details]
        lines += ["", f"Summary: {self.summary()}"]
        return "\n".join(lines)


def elapsed_ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def format_duration(ms: int) -> str:
    return f"{ms} ms" if ms < 1000 else f"{ms / 1000:.2f}s"


def format_list(items: list[str]) -> str:
    return ", ".join(items) if items else "none"


def format_tokens(stats: dict) -> str:
    """'model: x · tokens: 612 in / 148 out' from what `structured_call` recorded."""
    parts = [f"model: {stats.get('model', 'unknown')}"]
    if stats.get("input_tokens") is not None:
        parts.append(f"tokens: {stats['input_tokens']:,} in / {stats.get('output_tokens') or 0:,} out")
    return " · ".join(parts)
