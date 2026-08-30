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


class Trace:
    """One user question, rendered as a live-updating st.status() box."""

    def __init__(self, label: str):
        self._status = st.status(f"🔍 {label}", expanded=True)
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
        self._status.update(label=f"🤖 Asking {model}...")
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
        self._status.update(label=f"✅ Answered in {duration_ms}ms", state="complete", expanded=True)

    def emit_error(self, name: str, message: str, duration_ms: int):
        self._emit("ERROR", name, message, duration_ms)
        self._status.update(label=f"❌ {name}", state="error", expanded=True)


def start_user_action(label: str) -> Trace:
    return Trace(label)
