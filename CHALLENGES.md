# Challenges & solutions

A running log of the non-obvious problems hit while building and deploying
this project, and how each was resolved. Written for whoever (including
future-me) wonders "why is it built this way."

## 1. The System Design Panel only worked in local dev

**Problem:** the panel (a live trace of RETRIEVAL → CONTEXT_BUILD → LLM_CALL →
STREAMING → RESPONSE/ERROR) was built as a second HTTP server
(`sse_server.py`, stdlib `http.server`) on `localhost:8502`, broadcasting
events over Server-Sent Events to a hand-rolled `EventSource` client
(`system_design_panel.py`) embedded via `st.components.v1.html`. Every
single-port hosting platform — Hugging Face Spaces, Render, Streamlit
Community Cloud — can't expose that second port, so the panel just showed
"Reconnecting…" forever once deployed.

**First instinct (rejected):** the two options considered were an nginx
reverse proxy inside a custom Docker container (routes `/events` to the
internal SSE server, everything else to Streamlit), or hooking into
Streamlit's internal, undocumented Tornado server to mount a second route on
the same port. Both add real infrastructure — a Dockerfile, an nginx config,
a process supervisor, or a dependency on private Streamlit internals that
could break on a version bump — for what is fundamentally a demo feature.

**Actual root cause:** the two-port design was never necessary. Streamlit
already streams incremental UI updates to the browser over its own single
connection during a script run — that's literally how `st.spinner` and this
app's own `st.write_stream(...)` (the token-by-token answer) already worked.
A live trace panel didn't need a second server at all.

**Solution:** rewrote `workflow_events.py` to wrap `st.status()` directly —
a native Streamlit container with running/complete/error state, written to
incrementally as the pipeline executes. Deleted `sse_server.py` and
`system_design_panel.py` entirely: no queue, no thread, no port, no custom
JS. Works identically in local dev and on any single-port host, because there
is no longer a second port to be single about.

**Trade-off accepted:** the old design kept one always-mounted iframe that
accumulated a scrolling log of every trace across the whole browser session.
The new design is per-turn: the status box is created fresh each question and
only the most recently answered turn shows its trace (older turns just show
their answer text, since `st.session_state.messages` only ever stored plain
text, not trace objects). This was a deliberate simplification, not an
oversight — extending it to a cumulative log would mean serializing trace
data into session state and re-rendering it as a plain `st.expander` (not
`st.status`, which implies "currently happening") during history replay.
Not worth the complexity for a portfolio demo.

## 2. `st.status()` has two gotchas that would have silently broken the panel

Caught before shipping, via a second-opinion review of the redesign:

- **`expanded` resets to `False` on `.update()` unless re-asserted.** Calling
  `status.update(state="complete")` without also passing `expanded=True` in
  that same call collapses the box the instant the turn finishes — it looks
  fine while running, then silently hides the very thing it was built to
  show. Fixed by always passing `expanded=True` alongside `state=...` in the
  terminal `emit_response`/`emit_error` calls.
- **No `with` block means no automatic exception→error-state safety net.**
  `with st.status(...) as s:` catches any exception that escapes the block
  and force-sets `state="error"` before re-raising. Since `Trace` holds the
  status object directly (not via `with`, so different try/except branches in
  `app.py` can call `.update()` independently), an *unanticipated* exception
  — anything not already caught by the three explicit `anthropic.*` except
  clauses — would propagate past them and leave the status box stuck
  permanently spinning, which is a more embarrassing failure mode than a
  plain traceback would have been. Fixed with a catch-all
  `except Exception as e:` as the last branch, calling
  `trace.emit_error("UnexpectedError", str(e), ...)` before showing a
  generic error message. Verified with `AppTest` by deliberately raising a
  non-`anthropic` exception mid-stream and confirming the status box reaches
  `state="error"` instead of hanging.

## 3. Hugging Face Spaces quietly changed its SDK options

**Problem:** `DEPLOY.md` was written assuming "SDK: Streamlit" would be a
one-click choice on Hugging Face's *New Space* wizard, per their own
documentation. By the time we went to actually deploy, the wizard only
offered three SDKs: Gradio, Docker, and Static. Confirmed via HF's own
current docs (`spaces-overview.md`): *"The Hub offers three SDK options:
Gradio, Docker and static HTML."* Streamlit is no longer one of them.

**Compounding problem:** HF's docs also state that creating a Gradio or
Docker Space now requires a **paid PRO plan** for personal accounts (the free
exception is limited to up to 2 Gradio Spaces on ZeroGPU, which doesn't apply
here). Static Spaces can't run a Python backend at all, so none of the three
free-tier options could directly serve this app as originally planned.

**Solution:** pivoted the primary deploy target to **Streamlit Community
Cloud** — genuinely free, purpose-built for this exact framework, deploys
straight from the existing public GitHub repo with no Dockerfile, and
auto-redeploys on every push. This didn't require touching the app's
architecture at all, since after fixing the System Design Panel (item 1
above) the app has no port-dependent behavior left — it deploys the same way
on any single-port host. Hugging Face Spaces is documented as optional (for
the resume mention only): either pay for PRO + a minimal Dockerfile, or try
setting `sdk: streamlit` directly in the Space repo's README YAML frontmatter
(bypassing the wizard) to see if HF's backend still honors an SDK it no
longer surfaces in the UI — untested, flagged honestly as unconfirmed rather
than assumed to work.

## 4. Anthropic spend limits are account/workspace-scoped, not per-key

**Problem:** wanted a spend cap on this project's Claude usage without
affecting other unrelated projects sharing the same Anthropic account — but
Anthropic doesn't expose a spend limit on an individual API key.

**Solution:** Anthropic Console supports **Workspaces**, each with its own
API keys and its own billing/spend limit. Created a dedicated workspace for
this project; the spend cap applies only to keys issued inside it, leaving
the account's other workspace(s) untouched.

## 5. Model choice was a real cost lever, not a nice-to-have setting

**Problem:** the app originally let users pick between Claude Sonnet 5,
Haiku 4.5, and Opus 4.8 in the sidebar. For a portfolio demo with light,
unpredictable public traffic, giving visitors the option to run the most
expensive model wasn't buying anything — it was just unmanaged cost exposure
that also required annoying model-specific branching (Sonnet 5 and Opus 4.8
reject a non-default `temperature` with a 400; only Haiku 4.5 accepted it).

**Solution:** pinned generation to **Haiku 4.5 only** — the cheapest in the
lineup at this app's typical context size (~3,500 input / ~400 output tokens
per question): roughly $0.005/question versus ~$0.017 for Sonnet 5 and
~$0.028 for Opus 4.8. Removed the `MODELS` dict and the
`TEMPERATURE_CAPABLE_MODELS` branching entirely in favor of a single `MODEL`
constant, since there was no longer a second model to branch around.

## 6. `anthropic>=0.117` resolved to a different SDK version on Streamlit Cloud

**Problem:** first real end-to-end test on the deployed app (asking a real
question with a real API key) failed with
`Messages.stream() got an unexpected keyword argument 'temperature'` — a
Python-level `TypeError`, not an API error, meaning the installed SDK's
`.stream()` method signature didn't include `temperature` at all. This had
never been caught locally because prior verification either had no API key
(stopped before reaching the call) or used a mocked `anthropic.Anthropic`
client (see item 2's `AppTest` verification) that accepted arbitrary kwargs
and therefore couldn't catch a real signature mismatch.

**Root cause:** `requirements.txt` pinned `anthropic>=0.117` — open-ended.
Locally installed `anthropic==0.117.0` (confirmed via
`inspect.signature(client.messages.stream)`) does accept `temperature`, so
whatever pip resolved on Streamlit Cloud's build was evidently a different
version.

**Solution:** pinned the exact tested version — `anthropic==0.117.0` — so the
deployed environment can no longer drift from what's been locally verified.

**Lesson for future changes:** mocking a third-party SDK in tests (as the
`AppTest` verification did) proves the *calling code* is exception-safe, but
it cannot catch a real signature or API mismatch with the actual library —
that only surfaces on a real end-to-end run against the genuine dependency.
Worth remembering before treating a mocked test pass as full verification.

## 7. Local Windows dev environment friction (not app bugs, but worth noting)

A few things that looked like problems but were purely local-environment
quirks, in case they recur:

- `streamlit` invoked directly from the conda env's `Scripts/` directory
  failed with "Permission denied" under Git Bash on Windows — the shebang
  script isn't directly executable in that shell. Fixed by invoking
  `python -m streamlit run app.py` instead.
- A stale background Streamlit process from an earlier test session held
  port 8501, so a freshly launched process silently failed to bind while an
  *old* copy of the code kept serving requests — made it look like edits
  weren't taking effect. Fixed by explicitly finding and killing the process
  bound to the port before relaunching.
- Printing emoji (used in the trace's step icons) to a Windows terminal
  using the default `cp1252` encoding raised a `UnicodeEncodeError` in a
  standalone test script — not a bug in the app itself (Streamlit's own
  rendering path doesn't hit this), just a reminder to set
  `PYTHONIOENCODING=utf-8` when scripting against emoji-containing output on
  Windows.
