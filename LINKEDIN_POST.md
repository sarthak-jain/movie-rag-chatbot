# LinkedIn post draft

(Attach a 30-60s screen recording of the app answering 2-3 fun questions —
video posts get far more reach than links alone. Put the live URL in the
first comment or at the end of the post.)

---

I built and shipped my own AI movie chatbot 🎬, grounded in real answers
instead of hallucinated ones.

Ask it "what's that movie where a man fakes his own death?" and it searches
34,000 Wikipedia film plots, finds the right ones, and answers with sources.

Try it live: <YOUR SPACE URL>

Under the hood it's a full RAG (Retrieval-Augmented Generation) pipeline:

🔹 34k movie plots embedded with an open-source model (gte-small)
🔹 FAISS vector index for semantic search — prebuilt offline so hosting
   stays on the free CPU tier
🔹 Claude for grounded, streamed answers
🔹 Streamlit UI with knobs you can play with: model, temperature, top-k
   retrieval, release-year filter, and a "show retrieved movies" panel so
   you can see exactly what the LLM saw

Biggest lessons from taking a course notebook to a public product:

1️⃣ Local-only pieces (Ollama) don't survive deployment — swapping to a
   hosted LLM changed the architecture more than any other decision.
2️⃣ Pre-computing embeddings offline is the difference between "needs a GPU
   server" and "runs free forever" — even when generation itself isn't free.
3️⃣ Showing retrieved sources isn't just a debug tool — it's what makes
   users trust the answers.

Built as a follow-up to Project 2 of ByteByteGo's AI Engineer cohort
(customer-support RAG chatbot), redesigned around a public dataset anyone
can play with.

Code is public: <YOUR SPACE URL>/tree/main

#AIEngineering #RAG #LLM #GenAI #Python #OpenSource #BuildInPublic
