"""System Design Trace — renders live backend steps directly into a
Streamlit st.status() container as the RAG pipeline executes.

Replaces the old cross-process SSE panel (a second stdlib HTTP server plus a
hand-rolled EventSource client) that only worked in local dev. Streamlit
already streams UI updates to the browser over its own connection as the
script runs — that's how st.spinner and st.write_stream already work in this
app — so a live trace never needed a second server or a second port. This
version works identically in local dev and on any single-port host.
"""

import itertools
import time

import streamlit as st

ICONS = {
    "RETRIEVAL": "🔍", "CONTEXT_BUILD": "📦", "LLM_CALL": "🤖",
    "STREAMING": "📡", "RESPONSE": "✅", "ERROR": "❌",
}


PANEL_LABEL = "🔧 System Design Panel"


class Trace:
    """One user question, rendered as a live-updating st.status() box.

    `container` is anything exposing `.status()` — the `st` module itself,
    `st.sidebar`, or a placeholder from `st.container()` — so the panel can be
    pinned to a fixed spot (e.g. the sidebar) instead of wherever this class
    happens to be instantiated in the script.
    """

    def __init__(self, label: str, container=st):
        self._status = container.status(f"{PANEL_LABEL} — 🔍 {label}", expanded=True)
        self._step_no = itertools.count(1)
        self._start = time.monotonic()

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._start) * 1000)

    def _emit(self, step_type: str, name: str, detail: str, duration_ms: int):
        n = next(self._step_no)
        icon = ICONS.get(step_type, "•")
        self._status.write(f"{icon} **[{n}] {name}** — {detail} ({duration_ms}ms)")

    def emit_retrieval(self, top_k: int, year_range: tuple[int, int], hit_count: int, duration_ms: int):
        self._emit(
            "RETRIEVAL", "FAISS similarity search",
            f"top_k={top_k}, years {year_range[0]}-{year_range[1]} → {hit_count} hits",
            duration_ms,
        )

    def emit_context_build(self, movie_count: int, context_chars: int, duration_ms: int):
        self._emit(
            "CONTEXT_BUILD", "Prompt context assembled",
            f"{movie_count} movies → ~{context_chars // 4} tokens", duration_ms,
        )

    def emit_llm_call(self, model: str, context_chars: int):
        self._status.update(label=f"{PANEL_LABEL} — 🤖 Asking {model}...")
        self._emit(
            "LLM_CALL", f"Claude request ({model})",
            f"streaming call started, ~{context_chars // 4} context tokens", 0,
        )

    def emit_streaming(self, char_count: int, duration_ms: int):
        self._emit(
            "STREAMING", "Answer streamed",
            f"{char_count} chars streamed to client", duration_ms,
        )

    def emit_response(self, status_text: str, duration_ms: int):
        self._emit("RESPONSE", "Turn complete", status_text, duration_ms)
        # expanded=True must be re-asserted here — update() resets it to False otherwise.
        self._status.update(
            label=f"{PANEL_LABEL} — ✅ Answered in {duration_ms}ms", state="complete", expanded=True
        )

    def emit_error(self, name: str, message: str, duration_ms: int):
        self._emit("ERROR", name, message, duration_ms)
        self._status.update(label=f"{PANEL_LABEL} — ❌ {name}", state="error", expanded=True)


class NullTrace:
    """No-op stand-in used when the System Design Panel toggle is off."""

    def elapsed_ms(self) -> int:
        return 0

    def emit_retrieval(self, *args, **kwargs):
        pass

    def emit_context_build(self, *args, **kwargs):
        pass

    def emit_llm_call(self, *args, **kwargs):
        pass

    def emit_streaming(self, *args, **kwargs):
        pass

    def emit_response(self, *args, **kwargs):
        pass

    def emit_error(self, *args, **kwargs):
        pass


def start_user_action(label: str, container=st, enabled: bool = True):
    return Trace(label, container=container) if enabled else NullTrace()
