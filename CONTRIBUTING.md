# Picking up this project

Onboarding notes for collaborators. Read `README.md` first for what the app is;
this file is about how to develop it.

## Repo map

| File | Purpose |
|---|---|
| `app.py` | The whole Streamlit app: loads prebuilt artifacts, retrieves, calls Claude, renders chat + sidebar settings |
| `build_index.py` | Offline one-time script: downloads the dataset, embeds 32,924 movies, writes `data/` |
| `data/index.faiss` | FAISS `IndexFlatIP` over normalized gte-small vectors (cosine sim), committed via **git LFS** |
| `data/movies.parquet` | Metadata + plots, row-aligned with the FAISS index (row i ↔ vector i) |
| `DEPLOY.md` | Deployment: GitHub + Hugging Face Space, Anthropic API key |
| `.gitattributes` | LFS tracking for `data/*` — keep it if you regenerate artifacts |

## Local setup

```bash
# any Python 3.11+ env
pip install -r requirements.txt

# artifacts ship in the repo via LFS, so you do NOT need to rebuild the index.
# If you cloned without LFS content: git lfs install && git lfs pull

export ANTHROPIC_API_KEY=...   # your own key from console.anthropic.com
streamlit run app.py
```

Never commit a key. Locally use the env var (or `.streamlit/secrets.toml`,
which is gitignored territory — don't add it to git). In production the key
lives as a Hugging Face Space secret.

## Design decisions to preserve

1. **Hosting is free; generation is not.** Free HF Space (CPU), index prebuilt
   offline — but the Claude API is billed per-token with no free tier, so a
   funded Anthropic key with a spend limit is required. Don't add anything
   that needs a GPU server.
2. **No user-facing API key inputs.** Deliberately removed (trust anti-pattern
   for a public site). Host key only; degrade gracefully on quota/rate-limit errors.
3. **The app never embeds the corpus.** Only the query is embedded at runtime.
   If you change the embedding model or the dataset, rerun `build_index.py`
   (~15 min CPU) and commit the regenerated `data/` — app and index must use
   the same embedding model (`thenlper/gte-small`, 384 dims).
4. **Answers must stay grounded.** The system prompt forbids inventing movies;
   the sources expander shows exactly what the LLM saw. Keep both.

## Gotchas

- `.streamlit/config.toml` sets `fileWatcherType = "none"` because Streamlit's
  watcher crashes introspecting torch modules. Leave it.
- The retrieval oversamples (`k * 20`) then post-filters by year — a plain
  `k` search would return too few results when the year filter is narrow.
- Dataset covers films up to **2017** (that's the dataset's cutoff, not a bug).
- Claude model IDs get deprecated over time; they're centralized in the
  `MODELS` dict at the top of `app.py`.
- Sonnet 5 and Opus 4.8 reject a non-default `temperature` (400 error) —
  only Haiku 4.5 in the `MODELS` lineup accepts it (`TEMPERATURE_CAPABLE_MODELS`).

## Testing

No test suite yet (good first contribution). Until then, smoke-test with
Streamlit's harness:

```python
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("app.py", default_timeout=120)
at.run()
assert not at.exception
```

Retrieval sanity check: "how does Casablanca end" should rank **Casablanca
(1942)** first.

## Deployment flow

Two remotes, one repo: `origin` (GitHub, code home) and `space` (Hugging Face,
serves the site). After any change: push to both. Full steps in `DEPLOY.md`.

## Idea backlog (unclaimed)

- Evaluation harness: small golden set of question → expected-movie pairs,
  measure retrieval hit-rate before/after changes
- Hybrid retrieval (BM25 + dense) for exact-title queries
- Re-ranker (e.g. cross-encoder) on the top-50 before the LLM
- Extend the dataset past 2017 (needs a compatible plot source + rebuild)
- Chat-history-aware retrieval (currently only generation sees history;
  follow-up questions like "who directed it?" work, but "what else is like
  *that one*?" retrieves poorly)
