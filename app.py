"""MoviePlot AI - a RAG chatbot over ~34,000 Wikipedia movie plots.

Retrieval: gte-small embeddings + FAISS (prebuilt by build_index.py).
Generation: Groq API (free tier). Set GROQ_API_KEY as an env var / HF Space
secret, or paste a key in the sidebar.
"""

import os
import pathlib

import faiss
import pandas as pd
import streamlit as st
from groq import Groq
from sentence_transformers import SentenceTransformer

DATA_DIR = pathlib.Path(__file__).parent / "data"
EMBED_MODEL = "thenlper/gte-small"

MODELS = {
    "Llama 3.1 8B (fastest)": "llama-3.1-8b-instant",
    "Llama 3.3 70B (smartest)": "llama-3.3-70b-versatile",
    "GPT-OSS 20B": "openai/gpt-oss-20b",
}

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
    index = faiss.read_index(str(DATA_DIR / "index.faiss"))
    movies = pd.read_parquet(DATA_DIR / "movies.parquet")
    embedder = SentenceTransformer(EMBED_MODEL)
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


def stream_answer(client: Groq, model: str, temperature: float, context: str, history: list):
    messages = [{"role": "system", "content": SYSTEM_PROMPT.format(context=context)}]
    # Last few turns so follow-up questions ("who directed it?") keep working.
    messages += history[-6:]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=1024,
        stream=True,
    )
    for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


st.set_page_config(page_title="MoviePlot AI", page_icon="🎬", layout="centered")

st.title("🎬 MoviePlot AI")
st.caption(
    "Ask anything about ~34,000 movies — plots, characters, endings, or "
    "“what's that movie where...”. A RAG pipeline over Wikipedia film plots: "
    "FAISS + gte-small retrieval, Llama generation via Groq."
)

with st.sidebar:
    st.header("⚙️ Settings")
    model_label = st.selectbox("LLM", list(MODELS.keys()))
    temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.1,
                            help="Higher = more creative, lower = more factual")
    top_k = st.slider("Movies retrieved per question", 3, 10, 5,
                      help="How many plot summaries are passed to the LLM as context")
    year_range = st.slider("Release year filter", 1900, 2017, (1900, 2017))
    show_sources = st.toggle("Show retrieved movies", value=True)

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets.get("GROQ_API_KEY", None)
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
            "Generation is not configured. If you are hosting this app, set a "
            "GROQ_API_KEY secret (free key at console.groq.com)."
        )
        st.stop()

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching 34k movie plots..."):
            hits = retrieve(question, top_k, year_range)
        context = format_context(hits)

        answer = None
        try:
            answer = st.write_stream(
                stream_answer(Groq(api_key=api_key), MODELS[model_label],
                              temperature, context, st.session_state.messages)
            )
        except Exception as e:
            if "rate limit" in str(e).lower() or "429" in str(e):
                st.warning(
                    "The free demo quota is used up for now — please try again "
                    "in a little while. (The retrieved movies below still work!)"
                )
            else:
                st.error(f"Generation failed: {e}")

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
