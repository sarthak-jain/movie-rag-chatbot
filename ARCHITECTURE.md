# Architecture

## System overview

```mermaid
flowchart TD
    subgraph offline["Offline, one-time (build_index.py)"]
        DS["Wikipedia Movie Plots dataset\n(HF Hub, ~34k movies)"] --> EMB1["gte-small embedder\n(384-dim)"]
        EMB1 --> IDX["data/index.faiss\nFAISS IndexFlatIP"]
        DS --> PARQ["data/movies.parquet\ntitle, year, genre, director, plot"]
    end

    subgraph runtime["Runtime — single Streamlit process, single port"]
        USER(["User"]) -->|"question"| UI["app.py\nStreamlit UI + session state"]
        UI --> EMB2["gte-small embedder\n(same model, query only)"]
        EMB2 --> SEARCH["FAISS similarity search\ntop_k oversampled, year-filtered"]
        IDX -.->|"loaded once,\nst.cache_resource"| SEARCH
        PARQ -.->|"loaded once,\nst.cache_resource"| SEARCH
        SEARCH --> CTX["format_context()\nprompt assembly"]
        CTX --> CLAUDE["Claude Haiku 4.5\nAnthropic API, streamed"]
        CLAUDE -->|"token stream"| ANSWER["st.write_stream()\nchat bubble"]
        ANSWER --> USER

        SEARCH -.->|"emit_retrieval()"| TRACE["workflow_events.Trace\nst.status() box, inline per turn"]
        CTX -.->|"emit_context_build()"| TRACE
        CLAUDE -.->|"emit_llm_call() / emit_streaming()\nemit_response() / emit_error()"| TRACE
        TRACE -->|"live-updating,\nsame connection"| USER
    end

    subgraph hosting["Hosting"]
        GH["GitHub repo\n(origin, public, git-LFS for data/)"] -->|"push → auto-deploy"| SCC["Streamlit Community Cloud\nfree, primary target"]
        GH -.->|"optional, resume value"| HF["Hugging Face Space\noptional, paid Docker or\nunconfirmed sdk:streamlit"]
    end

    runtime -.->|"deployed as"| hosting
```

## Components

| Component | Role | Notes |
|---|---|---|
| `build_index.py` | Offline embedding + index build | Runs once (~15 min CPU); output committed via git LFS |
| `app.py` | The entire runtime app | UI, retrieval, prompt assembly, generation, all in one Streamlit script |
| `workflow_events.py` | System Design Panel | Thin wrapper over `st.status()` — no server, no queue |
| `data/index.faiss`, `data/movies.parquet` | Prebuilt retrieval corpus | Loaded once per process via `@st.cache_resource`, never rebuilt at runtime |
| Anthropic API (Claude Haiku 4.5) | Generation | Streamed via `client.messages.stream(...)`; only external network dependency at runtime |

## Why a single process, single port

The whole app — UI rendering, retrieval, prompt building, the Claude call,
and the live "System Design Panel" trace — runs inside **one Streamlit
script, over one WebSocket connection, on one port.** This wasn't the
original design (an earlier version ran a second stdlib HTTP server on a
second port purely to feed the trace panel via Server-Sent Events — see
`CHALLENGES.md` §1), but collapsing it to a single process turned out to be
both simpler *and* a hosting requirement: every free hosting platform
evaluated for this project (Hugging Face Spaces, Streamlit Community Cloud,
Render) exposes exactly one port per app. A design that depends on a second
port doesn't just fail on one of them — it fails on all of them.

## Request lifecycle (one question → one answer)

```mermaid
sequenceDiagram
    participant U as User (browser)
    participant S as app.py (Streamlit)
    participant F as FAISS index
    participant C as Claude Haiku 4.5

    U->>S: submits question
    S->>S: st.status() box opens (running)
    S->>F: embed query, search top_k (oversampled, year-filtered)
    F-->>S: hits (movies + similarity scores)
    S->>S: emit_retrieval() → status line
    S->>S: format_context() from hits
    S->>S: emit_context_build() → status line
    S->>C: stream request (system prompt + context + last 6 turns)
    S->>S: emit_llm_call() → status label updates
    loop token-by-token
        C-->>S: text delta
        S-->>U: st.write_stream renders incrementally
    end
    S->>S: emit_streaming(), emit_response() → status: complete, expanded
    S-->>U: chat bubble + sources expander + trace box, all inline
```

## Cost shape

- **Hosting:** $0 — Streamlit Community Cloud's free tier, or Hugging Face
  Spaces' free CPU Basic tier if the optional HF add-on is used.
- **Retrieval:** $0 at runtime — the embedding model and index are prebuilt
  and loaded once per process; only the user's query is embedded live, and
  that's local CPU inference, not a paid API call.
- **Generation:** the only per-request cost. Pinned to Claude Haiku 4.5
  specifically to minimize this (~$0.005/question at this app's typical
  context size) — see `CHALLENGES.md` §5 for the model-selection reasoning
  and `DEPLOY.md` for spend-limit setup via a dedicated Anthropic workspace.
