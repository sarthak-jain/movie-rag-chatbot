---
title: MoviePlot AI
emoji: 🎬
colorFrom: red
colorTo: indigo
sdk: streamlit
sdk_version: "1.45.1"
app_file: app.py
pinned: false
license: mit
---

# 🎬 MoviePlot AI

A retrieval-augmented (RAG) chatbot that answers questions about **~34,000 movies**
using their Wikipedia plot summaries. Ask *"what's that movie where a man fakes his
own death?"* or *"how does Casablanca end?"* and it finds the relevant plots and
answers grounded in them — with sources shown.

**Live demo:** _add your Space URL here_

## How it works

```
user question
     │
     ▼
gte-small embedding (384-dim)          ← same model used to embed all 34k plots
     │
     ▼
FAISS similarity search (cosine, prebuilt index)
     │  top-k plot summaries + metadata
     ▼
prompt with retrieved context
     │
     ▼
Claude (Anthropic API)  →  streamed, grounded answer + cited sources
```

- **Dataset:** [Wikipedia Movie Plots](https://huggingface.co/datasets/vishnupriyavr/wiki-movie-plots-with-summaries)
  (plot text © Wikipedia contributors, CC BY-SA)
- **Embeddings:** [`thenlper/gte-small`](https://huggingface.co/thenlper/gte-small) — small enough to run on the free CPU tier
- **Vector store:** FAISS `IndexFlatIP` over normalized vectors (exact cosine search)
- **LLM:** Claude via the Anthropic API (Sonnet 5 / Haiku 4.5 / Opus 4.8 — switchable in the UI)
- **Cost:** The index is prebuilt offline (`build_index.py`), so the app never embeds
  the corpus at runtime — only each user question. Generation is billed per-token by
  Anthropic; there is no free tier, so this requires a funded API key.

## Settings you can play with

- **LLM model** — trade speed vs. quality
- **Temperature** — factual vs. creative answers
- **Top-k retrieval** — how many plots are passed as context
- **Release-year filter** — restrict the search to an era
- **Show retrieved movies** — inspect exactly what the LLM saw (with similarity scores)

## Run locally

```bash
pip install -r requirements.txt
python build_index.py          # one-time: downloads dataset, builds data/ artifacts (~15 min)
export ANTHROPIC_API_KEY=...   # from console.anthropic.com
streamlit run app.py
```

## Project background

Built as a follow-up to Project 2 (customer-support RAG chatbot) of the
ByteByteGo AI Engineer cohort — same core pipeline (chunk → embed → FAISS →
prompt → LLM → Streamlit), redesigned around a public dataset, a hosted free-tier
LLM instead of local Ollama, and user-tunable retrieval settings.
