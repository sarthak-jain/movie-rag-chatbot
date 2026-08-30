# Deploying MoviePlot AI

**Primary target: Streamlit Community Cloud** — free, purpose-built for this
framework, deploys straight from the GitHub repo, no Dockerfile, auto-redeploys
on every push. Hugging Face Spaces is documented below as an optional add-on
(nice for a resume mention, not required) — its free tier no longer offers a
plain Streamlit SDK, and the Docker SDK now requires a paid plan.

Generation runs on the Claude API, which is billed per-token — there is no
free tier, so you need a funded Anthropic account regardless of where you
host. You need: github.com, streamlit.io (or huggingface.co if adding that
too), and console.anthropic.com.

## 1. Get an Anthropic API key

1. Sign up / log in at https://console.anthropic.com.
2. Create a **new Workspace** for this project (e.g. `movie-rag-chatbot`) so
   its spend is isolated from any other Anthropic usage on your account.
3. Inside that workspace: **API Keys** → **Create Key** → copy it somewhere safe.
4. Add billing and set a spend limit **on that workspace** — the app's traffic
   is token-metered, and this way a spend cap here can't affect other projects.

## 2. Push to GitHub

The `data/` artifacts are large binaries tracked with Git LFS (already
configured via `.gitattributes`; `git lfs install` once if you never have).
GitHub's free LFS quota (1 GB storage / 1 GB month bandwidth) covers them fine.

```powershell
# create an empty public repo named movie-rag-chatbot on github.com first
git remote add origin https://github.com/<your-github-username>/movie-rag-chatbot.git
git push -u origin main
```

The repo must stay **public** — Streamlit Community Cloud's free tier deploys
from public repos.

## 3. Deploy on Streamlit Community Cloud

1. Sign up / log in at https://share.streamlit.io with your GitHub account.
2. Click **New app** → pick this repo, branch `main`, file `app.py`.
3. Under **Advanced settings → Secrets**, add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
4. Click **Deploy**. It builds for a few minutes (installing torch is the
   slow part), then your chatbot is live at
   `https://<your-app-name>.streamlit.app`.
5. Every future `git push origin main` auto-redeploys — no second remote to
   remember.

**Verify before calling it done:** open the live URL, ask a real question,
confirm the answer streams and the System Design Panel and sources expander
both populate. Also confirm the `data/index.faiss` / `data/movies.parquet`
LFS files actually pulled correctly during the build (check the build logs,
or just confirm retrieval returns real movies rather than erroring) — LFS has
occasionally been reported as flaky on Community Cloud, so this is worth
eyeballing on the first deploy rather than assuming it worked.

Add the live URL to `README.md` and `LINKEDIN_POST.md`.

## Optional: also add a Hugging Face Space (resume value, not required)

Hugging Face's Space creation wizard no longer offers a plain "Streamlit" SDK
— only Gradio, Docker, and Static — and creating a Docker or Gradio Space now
requires a paid plan for personal accounts. Static can't run a Python
backend, so it's not viable for this app. Two ways to still get this on HF,
if you want it for the resume line despite the app already being live
elsewhere:

- **Pay for HF PRO** and use the Docker SDK with a minimal Dockerfile
  (`CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]`,
  `app_port: 7860` in the README YAML). Straightforward, but costs money for
  something that's optional.
- **Try creating the Space repo directly with `sdk: streamlit` in the README
  YAML frontmatter** (already present at the top of this repo's `README.md`),
  bypassing the picker wizard entirely, and see if HF's backend still honors
  it even though the UI no longer offers it as a choice. Free to attempt,
  unconfirmed whether it still works — HF's Docker/Gradio paid-plan
  restriction is specifically about those two SDKs, not about the CPU Basic
  hardware tier itself, so this may still work.

If you go this route: same steps as before — create the Space, add
`ANTHROPIC_API_KEY` as a secret under Settings → Variables and secrets, add a
`space` git remote, and push both remotes after any change:

```powershell
git remote add space https://huggingface.co/spaces/<your-hf-username>/movieplot-ai
git push space main
# after any future change: git push origin main; git push space main
```

## Notes on hosting and cost

- **Streamlit Community Cloud**: free, sleeps after a period of inactivity,
  wakes on the next visit. Fine for a portfolio.
- **Claude API**: billed per-token, no free tier. The model is pinned to
  Haiku 4.5 (cheapest in the Claude lineup) specifically to keep this cost
  near-zero for portfolio-level traffic. Set a workspace-scoped spend limit
  in the Anthropic console so a traffic burst can't run away. If the key ever
  hits a rate limit or the spend cap, the app shows a friendly "quota used up,
  try again later" message and retrieval (the sources panel) keeps working.
  Visitors are never asked for an API key — a public site asking users to
  paste keys is a trust anti-pattern.
