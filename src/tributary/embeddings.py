"""Local embeddings.

Runs on the machine rather than through an API: triage has to score every
ingested item, and paying per token to decide what to throw away would invert
the economics. fastembed uses ONNX, so this costs ~200MB rather than the ~2GB a
torch install would.

Vectors are L2-normalised, so cosine similarity is a plain dot product.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable, Sequence
from functools import lru_cache

import sqlite_vec

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
DIMENSION = 384  # must match the FLOAT[n] in migration 004
BATCH_SIZE = 64

# bge models put unrelated text around 0.5, so useful thresholds live in the
# upper half of the range. Never reason about these numbers as if 0 were the floor.
SIMILARITY_FLOOR = 0.5


@lru_cache(maxsize=2)
def get_model(name: str = DEFAULT_MODEL, threads: int | None = None):
    """Load the embedding model once per process (it takes a second to start).

    ONNX Runtime defaults conservatively on thread count; backfilling a few
    thousand items is the slowest thing this tool does, so use the cores.
    """
    from fastembed import TextEmbedding

    return TextEmbedding(name, threads=threads or os.cpu_count() or 1)


def embed(texts: Sequence[str], model_name: str = DEFAULT_MODEL) -> list[list[float]]:
    if not texts:
        return []
    model = get_model(model_name)
    return [vector.tolist() for vector in model.embed(list(texts))]


def embed_query(text: str, model_name: str = DEFAULT_MODEL) -> list[float]:
    return embed([text], model_name)[0]


def embedding_text(row: sqlite3.Row) -> str:
    """Build the text that represents an item in vector space.

    Titles alone are too sparse to separate topics, and full bodies drown the
    signal, so this is title plus the most identifying metadata per kind.
    """
    parts: list[str] = [row["title"] or ""]
    metadata = json.loads(row["metadata"] or "{}")
    kind = row["kind"]

    if kind == "model":
        # A model's identity is its task and tags; it has no prose.
        if tag := metadata.get("pipeline_tag"):
            parts.append(tag.replace("-", " "))
        tags = [t for t in metadata.get("tags", []) if ":" not in t][:12]
        parts.extend(tags)
    elif kind == "repo":
        parts.append((row["body"] or "")[:600])
    elif kind == "discussion":
        # The submitted link's domain is often the only topical hint a bare
        # headline gives ("arxiv.org" vs "techcrunch.com").
        if outbound := metadata.get("outbound_url"):
            parts.append(_domain(outbound))
        parts.append(row["summary"] or "")
    else:
        parts.append(row["summary"] or "")

    return " ".join(p for p in parts if p).strip()[:2000]


def _domain(url: str) -> str:
    from urllib.parse import urlsplit

    host = urlsplit(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def check_model(conn: sqlite3.Connection, model_name: str = DEFAULT_MODEL) -> None:
    """Record the model in use, and refuse to mix vectors from two models."""
    row = conn.execute("SELECT value FROM meta WHERE key = 'embedding_model'").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('embedding_model', ?)", (model_name,)
        )
        return
    if row["value"] != model_name:
        raise RuntimeError(
            f"database was embedded with {row['value']!r}, not {model_name!r}. "
            "Vectors from different models are not comparable — "
            "re-embed with `trib embed --reset` to switch."
        )


def pending(conn: sqlite3.Connection, limit: int | None = None) -> list[sqlite3.Row]:
    """Items whose vector is missing or stale relative to their content."""
    sql = """
        SELECT id, kind, title, summary, body, metadata, content_hash
          FROM items
         WHERE embedded_hash IS NULL OR embedded_hash != content_hash
         ORDER BY COALESCE(published_at, fetched_at) DESC
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    return list(conn.execute(sql))


def store(conn: sqlite3.Connection, rows: Iterable[sqlite3.Row], vectors: list[list[float]]) -> int:
    """Write vectors for ``rows``, marking each item embedded at its current hash."""
    written = 0
    for row, vector in zip(rows, vectors, strict=True):
        conn.execute("DELETE FROM item_vectors WHERE item_id = ?", (row["id"],))
        conn.execute(
            "INSERT INTO item_vectors (item_id, embedding) VALUES (?, ?)",
            (row["id"], sqlite_vec.serialize_float32(vector)),
        )
        # Coalesce to "" rather than storing NULL: a NULL marker is
        # indistinguishable from "never embedded", so a row whose content_hash
        # is NULL would be re-embedded on every run forever. Rows predating the
        # content_hash column are exactly that case.
        conn.execute(
            "UPDATE items SET embedded_hash = ? WHERE id = ?",
            (row["content_hash"] or "", row["id"]),
        )
        written += 1
    return written
