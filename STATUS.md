# Project status

Last updated: 2026-07-19

## Done so far

- Full RAG app built: FAISS + `gte-small` retrieval over ~34k Wikipedia movie
  plots, prebuilt offline via `build_index.py`.
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

## What's left to deploy

1. **Get an Anthropic API key** at console.anthropic.com, add billing, and set
   a spend limit (Claude has no free tier, unlike the old Groq setup).
2. **Smoke-test locally** with that key — `export ANTHROPIC_API_KEY=...` then
   `streamlit run app.py` — to confirm a real Claude answer streams correctly
   before deploying.
3. **Create the Hugging Face Space**: SDK Streamlit, hardware CPU basic
   (free), visibility public. Add secret `ANTHROPIC_API_KEY` under
   Settings → Variables and secrets.
4. **Add the `space` git remote** and push:
   ```
   git remote add space https://huggingface.co/spaces/<your-hf-username>/movieplot-ai
   git push space main
   ```
5. **Verify the live Space** once it builds (~a few minutes — installing
   torch is the slow part): ask it a real question, confirm streaming works
   and the sources panel populates.
6. Add the live Space URL to `README.md` and `LINKEDIN_POST.md` (both have
   `<YOUR SPACE URL>` / "add your Space URL here" placeholders).

## Key facts for whoever resumes this

- Full step-by-step deploy instructions: `DEPLOY.md`.
- Repo map / design decisions / gotchas: `CONTRIBUTING.md`.
- Env var is `ANTHROPIC_API_KEY` (local: shell export or
  `.streamlit/secrets.toml`, gitignored; production: HF Space secret).
- Model IDs are centralized in the `MODELS` dict at the top of `app.py`.
