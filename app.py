"""MoviePlot AI - a RAG chatbot over ~34,000 Wikipedia movie plots.

Retrieval: gte-small embeddings + FAISS (prebuilt by build_index.py).
Generation: Claude API. Set ANTHROPIC_API_KEY as an env var / HF Space secret.
"""

import os
import pathlib
import time

import anthropic
import faiss
import pandas as pd
import streamlit as st
from sentence_transformers import SentenceTransformer

import sse_server
import system_design_panel
import workflow_events

DATA_DIR = pathlib.Path(__file__).parent / "data"
EMBED_MODEL = "thenlper/gte-small"

MODELS = {
    "Claude Sonnet 5 (balanced)": "claude-sonnet-5",
    "Claude Haiku 4.5 (fastest, cheapest)": "claude-haiku-4-5",
    "Claude Opus 4.8 (smartest)": "claude-opus-4-8",
}
# Sonnet 5 / Opus 4.8 reject non-default sampling params (400); only Haiku 4.5
# in this lineup accepts a custom temperature.
TEMPERATURE_CAPABLE_MODELS = {"claude-haiku-4-5"}

SYSTEM_PROMPT = """You are MoviePlot AI, a movie expert chatbot grounded in a database of \
Wikipedia film plot summaries. Answer the user's question using ONLY the movie context \
provided below.

Rules:
1. Base your answer only on the CONTEXT. If none of the retrieved movies answer the \
question, say so honestly and suggest the user rephrase.
2. When you mention a movie, always give its title in bold with the year, e.g. \
**The Matrix** (1999).
3. Be conversational and concise. If several retrieved movies fit, compare the best 2-3.
4. Never invent movies or plot details that are not in the CONTEXT.

CONTEXT:
{context}"""


@st.cache_resource(show_spinner="Loading index and embedding model...")
def load_resources():
    trace = workflow_events.start_system_event("Startup")
    t0 = time.monotonic()
    index = faiss.read_index(str(DATA_DIR / "index.faiss"))
    movies = pd.read_parquet(DATA_DIR / "movies.parquet")
    embedder = SentenceTransformer(EMBED_MODEL)
    trace.emit_index_loaded(index.ntotal, index.d, EMBED_MODEL, int((time.monotonic() - t0) * 1000))
    return index, movies, embedder


def retrieve(query: str, k: int, year_range: tuple[int, int]) -> pd.DataFrame:
    index, movies, embedder = load_resources()
    vector = embedder.encode([query], normalize_embeddings=True)
    # Oversample so we can post-filter by year and still return k results.
    scores, ids = index.search(vector, min(k * 20, index.ntotal))
    hits = movies.iloc[ids[0]].copy()
    hits["score"] = scores[0]
    hits = hits[(hits["year"] >= year_range[0]) & (hits["year"] <= year_range[1])]
    return hits.head(k)


def format_context(hits: pd.DataFrame) -> str:
    blocks = []
    for row in hits.itertuples():
        blocks.append(
            f"[{row.title} ({row.year}) | genre: {row.genre} | director: {row.director}]\n"
            f"{row.plot}"
        )
    return "\n\n---\n\n".join(blocks)


def stream_answer(client: anthropic.Anthropic, model: str, temperature: float, context: str, history: list):
    kwargs = dict(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT.format(context=context),
        # Last few turns so follow-up questions ("who directed it?") keep working.
        messages=history[-6:],
    )
    if model in TEMPERATURE_CAPABLE_MODELS:
        kwargs["temperature"] = temperature
    with client.messages.stream(**kwargs) as stream:
        yield from stream.text_stream


st.set_page_config(page_title="RAG-Based Chatbot for Movies", page_icon="🎬", layout="centered")

sse_port = sse_server.start_server_once()

st.title("🎬 RAG-Based Chatbot for Movies")
st.caption(
    "A Retrieval-Augmented Generation chatbot grounded in ~34,000 Wikipedia film "
    "plots. Ask about plots, characters, endings, or “what's that movie where...” — "
    "your question is matched against the full corpus (FAISS + gte-small embeddings) "
    "and Claude answers using only the retrieved plots."
)

with st.expander("🔧 System Design Panel — live backend events (SSE)"):
    st.caption(
        "Streams retrieval, context-building, and Claude-call events straight off the "
        "request pipeline via Server-Sent Events. **Local dev only** — connects to a "
        "second local server on `localhost:8502`; on a single-port host like Hugging "
        "Face Spaces this will show *Reconnecting…* since that port isn't reachable."
    )
    st.components.v1.html(system_design_panel.render_html(sse_port), height=480, scrolling=True)

with st.sidebar:
    st.header("⚙️ Settings")
    model_label = st.selectbox("LLM", list(MODELS.keys()))
    temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.1,
                            help="Higher = more creative, lower = more factual. "
                                 "Only applies to Haiku 4.5 — Sonnet 5 and Opus 4.8 "
                                 "always use their default sampling.")
    top_k = st.slider("Movies retrieved per question", 3, 10, 5,
                      help="How many plot summaries are passed to the LLM as context")
    year_range = st.slider("Release year filter", 1900, 2017, (1900, 2017))
    show_sources = st.toggle("Show retrieved movies", value=True)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets.get("ANTHROPIC_API_KEY", None)
        except Exception:  # no secrets.toml at all
            api_key = None

    st.divider()
    st.markdown(
        "Built by **Sarthak Jain** · "
        "[Dataset](https://huggingface.co/datasets/vishnupriyavr/wiki-movie-plots-with-summaries) · "
        "plots © Wikipedia (CC BY-SA)"
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if not st.session_state.messages:
    st.markdown("**Try one of these:**")
    examples = [
        "What's that movie where a man fakes his own death?",
        "Recommend a 90s sci-fi movie about virtual reality",
        "How does Casablanca end?",
    ]
    cols = st.columns(len(examples))
    for col, example in zip(cols, examples):
        if col.button(example, use_container_width=True):
            st.session_state.pending = example
            st.rerun()

question = st.chat_input("Ask about a movie plot...")
if not question and "pending" in st.session_state:
    question = st.session_state.pop("pending")

if question:
    if not api_key:
        st.error(
            "Generation is not configured. If you are hosting this app, set an "
            "ANTHROPIC_API_KEY secret (console.anthropic.com)."
        )
        st.stop()

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    trace = workflow_events.start_user_action(question[:60])

    with st.chat_message("assistant"):
        with st.spinner("Searching 34k movie plots..."):
            t0 = time.monotonic()
            hits = retrieve(question, top_k, year_range)
            trace.emit_retrieval(top_k, year_range, len(hits), int((time.monotonic() - t0) * 1000))

        t0 = time.monotonic()
        context = format_context(hits)
        trace.emit_context_build(len(hits), len(context), int((time.monotonic() - t0) * 1000))

        answer = None
        try:
            trace.emit_llm_call(MODELS[model_label], len(context))
            t0 = time.monotonic()
            answer = st.write_stream(
                stream_answer(anthropic.Anthropic(api_key=api_key), MODELS[model_label],
                              temperature, context, st.session_state.messages)
            )
            trace.emit_streaming(len(answer) if answer else 0, int((time.monotonic() - t0) * 1000))
            trace.emit_response("200 OK · grounded answer", trace.elapsed_ms())
        except anthropic.RateLimitError:
            trace.emit_error("RateLimitError", "quota exhausted", trace.elapsed_ms())
            st.warning(
                "The demo quota is used up for now — please try again "
                "in a little while. (The retrieved movies below still work!)"
            )
        except anthropic.APIStatusError as e:
            trace.emit_error("APIStatusError", e.message, trace.elapsed_ms())
            st.error(f"Generation failed: {e.message}")
        except anthropic.APIConnectionError:
            trace.emit_error("APIConnectionError", "network error", trace.elapsed_ms())
            st.error("Couldn't reach the Claude API — check your connection and try again.")

        if show_sources and not hits.empty:
            with st.expander(f"📚 {len(hits)} retrieved movies"):
                for row in hits.itertuples():
                    st.markdown(
                        f"**[{row.title}]({row.wiki_url})** ({row.year}) · {row.genre} · "
                        f"dir. {row.director} · similarity {row.score:.2f}\n\n"
                        f"> {row.summary}"
                    )

    if answer:
        st.session_state.messages.append({"role": "assistant", "content": answer})
