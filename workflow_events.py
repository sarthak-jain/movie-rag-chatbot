"""In-process pub/sub for the System Design Panel.

Mirrors the trace/step model of a typical backend observability panel:
a "trace" (one user question, or a one-off system event) contains an ordered
list of "steps" (retrieval, context build, LLM call, streaming, response).
Steps are broadcast to any subscribed SSE client via `sse_server.py`.
"""

import itertools
import queue
import threading
import time
import uuid

_lock = threading.Lock()
_subscribers: list[queue.Queue] = []
_counters = itertools.count(1)


def subscribe() -> queue.Queue:
    q: queue.Queue = queue.Queue(maxsize=200)
    with _lock:
        _subscribers.append(q)
    return q


def unsubscribe(q: queue.Queue) -> None:
    with _lock:
        if q in _subscribers:
            _subscribers.remove(q)


def _publish(event_name: str, data: dict) -> None:
    with _lock:
        targets = list(_subscribers)
    for q in targets:
        try:
            q.put_nowait((event_name, data))
        except queue.Full:
            pass  # slow client — drop rather than block the pipeline


class Trace:
    """One user question or system event, made up of ordered steps."""

    def __init__(self, trace_id: str, trace_type: str, label: str):
        self.trace_id = trace_id
        self.trace_type = trace_type
        self._step_no = itertools.count(1)
        self._start = time.monotonic()
        _publish("trace-start", {
            "traceId": trace_id,
            "traceType": trace_type,
            "label": label,
            "timestamp": int(time.time() * 1000),
        })

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._start) * 1000)

    def _emit(self, step_type: str, name: str, detail: str, duration_ms: int, **metadata):
        _publish("workflow-step", {
            "traceId": self.trace_id,
            "traceType": self.trace_type,
            "stepNumber": next(self._step_no),
            "type": step_type,
            "name": name,
            "detail": detail,
            "durationMs": duration_ms,
            "metadata": metadata,
            "timestamp": int(time.time() * 1000),
        })

    def emit_index_loaded(self, vector_count: int, dims: int, embed_model: str, duration_ms: int):
        self._emit(
            "INDEX_LOAD", "FAISS index + embedder loaded",
            f"{vector_count:,} vectors, {dims} dims ({embed_model})",
            duration_ms, vectors=vector_count,
        )

    def emit_retrieval(self, top_k: int, year_range: tuple[int, int], hit_count: int, duration_ms: int):
        self._emit(
            "RETRIEVAL", "FAISS similarity search",
            f"top_k={top_k}, years {year_range[0]}-{year_range[1]} → {hit_count} hits",
            duration_ms, topK=top_k, hits=hit_count,
        )

    def emit_context_build(self, movie_count: int, context_chars: int, duration_ms: int):
        self._emit(
            "CONTEXT_BUILD", "Prompt context assembled",
            f"{movie_count} movies → ~{context_chars // 4} tokens",
            duration_ms, movies=movie_count,
        )

    def emit_llm_call(self, model: str, context_chars: int):
        self._emit(
            "LLM_CALL", f"Claude request ({model})",
            f"streaming call started, ~{context_chars // 4} context tokens",
            0, model=model,
        )

    def emit_streaming(self, char_count: int, duration_ms: int):
        self._emit(
            "STREAMING", "Answer streamed",
            f"{char_count} chars streamed to client",
            duration_ms, chars=char_count,
        )

    def emit_response(self, status: str, duration_ms: int):
        self._emit("RESPONSE", "Turn complete", status, duration_ms)

    def emit_error(self, name: str, message: str, duration_ms: int):
        self._emit("ERROR", name, message, duration_ms)


def start_user_action(label: str) -> Trace:
    return Trace(f"user-{uuid.uuid4().hex[:8]}", "USER_ACTION", label)


def start_system_event(label: str) -> Trace:
    return Trace(f"sys-{next(_counters)}", "SYSTEM_EVENT", label)
