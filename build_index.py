"""Build the FAISS index for MoviePlot AI.

Run this once locally (it takes ~10-20 min on CPU):

    python build_index.py

It downloads the Wikipedia Movie Plots dataset (~35k movies) from the
Hugging Face Hub, embeds one vector per movie with gte-small, and writes:

    data/movies.parquet   - movie metadata + plots (the retrieval payload)
    data/index.faiss      - FAISS index of normalized embeddings (cosine sim)

The deployed app only loads these two artifacts; it never re-embeds.
"""

import pathlib

import faiss
import numpy as np
import pandas as pd
from huggingface_hub import hf_hub_download
from sentence_transformers import SentenceTransformer

DATASET_REPO = "vishnupriyavr/wiki-movie-plots-with-summaries"
DATASET_FILE = "wiki_movie_plots_deduped_with_summaries.csv"
EMBED_MODEL = "thenlper/gte-small"
MAX_PLOT_CHARS = 2500  # keep the payload small; enough context for the LLM
OUT_DIR = pathlib.Path(__file__).parent / "data"


def load_and_clean() -> pd.DataFrame:
    csv_path = hf_hub_download(repo_id=DATASET_REPO, filename=DATASET_FILE, repo_type="dataset")
    df = pd.read_csv(csv_path)
    print(f"Downloaded {len(df)} rows")

    df = df.rename(
        columns={
            "Release Year": "year",
            "Title": "title",
            "Origin/Ethnicity": "origin",
            "Director": "director",
            "Genre": "genre",
            "Wiki Page": "wiki_url",
            "Plot": "plot",
            "PlotSummary": "summary",
        }
    )

    df["title"] = df["title"].astype(str).str.strip()
    df["summary"] = df["summary"].astype(str).str.strip()
    df["plot"] = df["plot"].astype(str).str.strip()
    df["genre"] = df["genre"].fillna("unknown").astype(str).str.strip()
    df["director"] = df["director"].fillna("Unknown").astype(str).str.strip()

    df = df[(df["summary"].str.len() > 40) & (df["plot"].str.len() > 200)]
    df = df.drop_duplicates(subset=["title", "year"]).reset_index(drop=True)
    df["plot"] = df["plot"].str.slice(0, MAX_PLOT_CHARS)

    print(f"Kept {len(df)} movies after cleaning")
    return df[["title", "year", "origin", "director", "genre", "wiki_url", "summary", "plot"]]


def embed(df: pd.DataFrame) -> np.ndarray:
    # Title/year/genre in the embedded text lets queries like
    # "90s sci-fi movie about ..." match on metadata, not just plot.
    texts = [
        f"{row.title} ({row.year}). Genre: {row.genre}. {row.summary}"
        for row in df.itertuples()
    ]
    model = SentenceTransformer(EMBED_MODEL)
    vectors = model.encode(
        texts,
        batch_size=128,
        show_progress_bar=True,
        normalize_embeddings=True,  # normalized + inner product = cosine similarity
    )
    return np.asarray(vectors, dtype=np.float32)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    df = load_and_clean()
    vectors = embed(df)

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    faiss.write_index(index, str(OUT_DIR / "index.faiss"))
    df.to_parquet(OUT_DIR / "movies.parquet", index=False)
    print(f"Wrote {index.ntotal} vectors ({vectors.shape[1]} dims) to {OUT_DIR}")


if __name__ == "__main__":
    main()
