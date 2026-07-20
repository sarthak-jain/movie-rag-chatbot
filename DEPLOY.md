# Deploying MoviePlot AI

One git repo, two remotes:

- **GitHub** (`origin`) — the public code home for your portfolio.
- **Hugging Face Space** (`space`) — what actually builds and serves the site.

Hosting is free (GitHub + HF Spaces CPU basic). Generation runs on the Claude
API, which is billed per-token — there is no free tier, so you need a funded
Anthropic account. You need: github.com, huggingface.co, and
console.anthropic.com.

## 1. Get an Anthropic API key

1. Sign up / log in at https://console.anthropic.com.
2. Go to **API Keys** → **Create Key** → copy it somewhere safe.
3. Add billing (Settings → Billing) — the app's traffic is token-metered, so
   set a spend limit you're comfortable with.

## 2. Create the Space

1. Sign up / log in at https://huggingface.co.
2. Click your avatar → **New Space**.
3. Name: `movieplot-ai` (or anything). License: MIT.
4. SDK: **Streamlit**. Hardware: **CPU basic (free)**. Visibility: **Public**.
5. Create the Space, then open **Settings → Variables and secrets** →
   **New secret**: name `ANTHROPIC_API_KEY`, value = your Anthropic key.

## 3. Push to GitHub

The `data/` artifacts are large binaries tracked with Git LFS (already
configured via `.gitattributes`; `git lfs install` once if you never have).
GitHub's free LFS quota (1 GB storage / 1 GB month bandwidth) covers them fine.

```powershell
# create an empty public repo named movie-rag-chatbot on github.com first
git remote add origin https://github.com/<your-github-username>/movie-rag-chatbot.git
git push -u origin main
```

## 4. Push the same repo to the Space

```powershell
# use a HF token with "write" scope from https://huggingface.co/settings/tokens
# as the password when prompted
git remote add space https://huggingface.co/spaces/<your-hf-username>/movieplot-ai
git push space main
```

After any future change: `git push origin main; git push space main`.

## 5. Done

The Space builds for a few minutes (installing torch is the slow part), then your
chatbot is live at `https://huggingface.co/spaces/<your-username>/movieplot-ai`.
Add that URL to the README and your LinkedIn post.

## Notes on hosting and cost

- **HF Spaces CPU basic**: free forever; the Space sleeps after ~48h of no
  traffic and cold-starts in ~1-2 min on the next visit. Fine for a portfolio.
- **Claude API**: billed per-token, no free tier. Set a monthly spend limit in
  the Anthropic console so a traffic burst can't run away. If the key ever
  hits a rate limit or the spend cap, the app shows a friendly "quota used up,
  try again later" message and retrieval (the sources panel) keeps working.
  Visitors are never asked for an API key — a public site asking users to paste
  keys is a trust anti-pattern.
