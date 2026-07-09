# Deploying MoviePlot AI (free)

One git repo, two remotes:

- **GitHub** (`origin`) — the public code home for your portfolio.
- **Hugging Face Space** (`space`) — what actually builds and serves the site.

Total cost: $0. You need three free accounts: github.com, huggingface.co,
and console.groq.com.

## 1. Get a free Groq API key

1. Sign up at https://console.groq.com (no credit card).
2. Go to **API Keys** → **Create API Key** → copy it somewhere safe.

## 2. Create the Space

1. Sign up / log in at https://huggingface.co.
2. Click your avatar → **New Space**.
3. Name: `movieplot-ai` (or anything). License: MIT.
4. SDK: **Streamlit**. Hardware: **CPU basic (free)**. Visibility: **Public**.
5. Create the Space, then open **Settings → Variables and secrets** →
   **New secret**: name `GROQ_API_KEY`, value = your Groq key.

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

## Notes on the free tiers

- **HF Spaces CPU basic**: free forever; the Space sleeps after ~48h of no
  traffic and cold-starts in ~1-2 min on the next visit. Fine for a portfolio.
- **Groq free tier**: generous per-day request limits per model. If a burst of
  LinkedIn visitors ever exhausts it, the app shows the API error and visitors
  can paste their own free key in the sidebar — so the demo never fully breaks.
