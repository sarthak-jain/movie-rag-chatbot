# Project status

Last updated: 2026-08-30

## 2026-08-30 update

- **Model pinned to Haiku 4.5 only.** Removed the Sonnet 5 / Opus 4.8 picker —
  Haiku 4.5 is cheapest in the Claude lineup (~$0.005/question vs. ~$0.017 for
  Sonnet 5 and ~$0.028 for Opus 4.8 at this app's typical context size), and
  it's the only one of the three that accepts a non-default `temperature`.
  `MODELS` dict + `TEMPERATURE_CAPABLE_MODELS` replaced with a single `MODEL`
  constant in `app.py`.
- **System Design Panel resolved — no longer local-dev only.** The old
  two-port SSE architecture (`sse_server.py` + `system_design_panel.py`) is
  deleted. `workflow_events.py` now wraps `st.status()` directly — Streamlit
  already streams UI updates to the browser over its own connection during a
  script run (that's how `st.write_stream` already worked), so the second
  HTTP server and pub/sub were never actually necessary. The panel now
  appears live, inline, per question, on **any** host — local or deployed —
  for zero extra infrastructure. Trade-off: it's per-turn now, not a
  cumulative cross-session log like the old always-mounted iframe was —
  intentional simplification, not a regression to fix later. See
  `CONTRIBUTING.md` gotchas for the two `st.status()` details that mattered
  (`expanded` resets on `.update()`; no `with` block means a manual catch-all
  `except Exception` is needed to avoid a stuck spinner on an unanticipated
  error).
- **Hosting target changed.** Hugging Face's Space-creation wizard no longer
  offers a plain "Streamlit" SDK (only Gradio/Docker/Static), and creating a
  Docker or Gradio Space now requires a paid plan for personal accounts.
  Since the System Design Panel no longer needs HF Spaces' specific
  single-process model to "sort of work" and cost matters more than the HF
  resume mention, **Streamlit Community Cloud** is now the primary documented
  deploy target — genuinely free, deploys straight from the same GitHub repo,
  no Dockerfile needed. HF Spaces is now optional (see `DEPLOY.md`), either
  paying for PRO + Docker, or trying `sdk: streamlit` directly in the README
  YAML to see if HF's backend still honors it despite the wizard no longer
  offering it — unconfirmed either way.
- **Anthropic spend isolation.** Recommended flow updated to use a dedicated
  Anthropic **Workspace** (not just a new key) for this project's spend
  limit, so it can't affect API usage on other unrelated projects sharing the
  same Anthropic account.
- Not yet done: an actual Streamlit Community Cloud deploy attempt (to
  confirm git-LFS pulls `data/index.faiss`/`data/movies.parquet` cleanly
  there — flagged as a real unknown, not assumed to "just work").

## Done so far

- Full RAG app built: FAISS + `gte-small` retrieval over ~34k Wikipedia movie
  plots, prebuilt offline via `build_index.py`.
- Added a **System Design Panel** (expandable, in the main page) that streams
  live backend events — retrieval, context build, Claude call, streaming,
  response/error — over real Server-Sent Events as questions are asked.
  Inspired by the workflow panel in `RealTimeSoccerDashboard`, adapted to fit
  Streamlit's single-process model:
  - `workflow_events.py` — trace/step pub-sub (pure Python, no Streamlit dep).
  - `sse_server.py` — stdlib `http.server`-based SSE server on `localhost:8502`,
    started once per process from `app.py`.
  - `system_design_panel.py` — the `EventSource`-based HTML/JS client,
    rendered via `st.components.v1.html`.
  - **Local dev only, by design** — HF Spaces exposes a single port, so this
    can't reach a real backend once deployed; the panel will show
    "Reconnecting…" there. Confirmed working end-to-end locally (screenshot
    showed the full trace: `RETRIEVAL` → `CONTEXT_BUILD` → `LLM_CALL` →
    `ERROR`/`RESPONSE`, plus a startup `INDEX_LOAD` system event).
  - No new dependencies — everything is Python stdlib.
- Generation switched from Groq (Llama) to the **Anthropic API** — `app.py`
  now calls Claude directly via the `anthropic` SDK.
  - Model picker: **Claude Sonnet 5** (balanced, default), **Claude Haiku 4.5**
    (fastest/cheapest), **Claude Opus 4.8** (smartest).
  - Streaming via `client.messages.stream(...)`; system prompt passed as the
    top-level `system` param.
  - `temperature` is only sent for Haiku 4.5 — Sonnet 5 and Opus 4.8 reject a
    non-default `temperature`/`top_p`/`top_k` with a 400.
  - Typed error handling (`anthropic.RateLimitError` / `APIStatusError` /
    `APIConnectionError`) with a friendly "quota used up" message instead of a
    crash.
- UI retitled to "🎬 RAG-Based Chatbot for Movies" with an updated description.
- Docs updated to match the Claude switch: `README.md`, `DEPLOY.md`,
  `CONTRIBUTING.md`, `LINKEDIN_POST.md`, `requirements.txt` (now installs
  `anthropic`, not `groq`).
- Verified locally in the `rag_chatbot` conda env: app imports cleanly,
  launches, syntax OK, retrieval sanity check passes ("how does Casablanca
  end" → **Casablanca (1942)** ranks first). **Not yet verified:** an actual
  end-to-end Claude answer — no `ANTHROPIC_API_KEY` was available in the dev
  environment used so far.
- Latest commit (`38c82a0`, "Switch generation from Groq to the Anthropic
  API") is pushed to `origin` (GitHub: `sarthak-jain/movie-rag-chatbot`, branch
  `main`).

## Resolved: making the System Design Panel work in production

Was paused (two options considered: nginx reverse proxy in a Docker
container, or hooking into Streamlit's internal Tornado server — both real
infra for a demo feature). Resolved instead by removing the second port
entirely — see the 2026-08-30 entry above. Neither option above was needed.

## What's left to deploy

1. **Get an Anthropic API key** in a dedicated Workspace at
   console.anthropic.com, add billing, and set a spend limit scoped to that
   workspace (Claude has no free tier).
2. **Smoke-test locally** with that key — `export ANTHROPIC_API_KEY=...` then
   `streamlit run app.py` — to confirm a real Claude answer streams correctly
   before deploying.
3. **Deploy on Streamlit Community Cloud** (primary target — see `DEPLOY.md`):
   sign in with GitHub at share.streamlit.io, point it at this repo, add
   `ANTHROPIC_API_KEY` under Advanced settings → Secrets, deploy.
4. **Verify the live app**: ask it a real question, confirm streaming works,
   the System Design Panel renders inline, and the sources panel populates.
   Also confirm the git-LFS `data/` files pulled correctly during the build.
5. Add the live app URL to `README.md` and `LINKEDIN_POST.md` (both have
   placeholders).
6. Optional: add a Hugging Face Space too, per `DEPLOY.md`'s optional section
   (requires either paying for PRO + Docker, or trying the unconfirmed
   `sdk: streamlit`-via-YAML approach).

## Key facts for whoever resumes this

- Full step-by-step deploy instructions: `DEPLOY.md`.
- Repo map / design decisions / gotchas: `CONTRIBUTING.md`.
- Env var is `ANTHROPIC_API_KEY` (local: shell export or
  `.streamlit/secrets.toml`, gitignored; production: the host's secret store).
- The model is centralized in the `MODEL` constant at the top of `app.py`.
