from __future__ import annotations

import json
import sqlite3

import pytest

from tributary import embeddings


def row(**fields) -> sqlite3.Row:
    """Build a Row-like mapping matching what embeddings.pending() selects."""
    base = {
        "id": 1, "kind": "article", "title": "", "summary": None,
        "body": None, "metadata": "{}", "content_hash": "h",
    }
    return base | fields


def test_article_uses_title_and_summary():
    text = embeddings.embedding_text(row(title="A new model", summary="It is fast."))
    assert text == "A new model It is fast."


def test_model_uses_task_and_tags_since_it_has_no_prose():
    text = embeddings.embedding_text(
        row(
            kind="model",
            title="deepseek-ai/DeepSeek-V4",
            metadata=json.dumps(
                {"pipeline_tag": "image-text-to-text", "tags": ["transformers", "vision"]}
            ),
        )
    )
    assert "image text to text" in text  # hyphens would tokenise badly
    assert "transformers" in text and "vision" in text


def test_model_tags_drop_namespaced_noise():
    """Tags like 'license:apache-2.0' or 'base_model:x' say nothing about topic."""
    text = embeddings.embedding_text(
        row(
            kind="model",
            title="org/m",
            metadata=json.dumps({"tags": ["license:mit", "arxiv:2609.1", "text-generation"]}),
        )
    )
    assert "license:mit" not in text
    assert "text-generation" in text


def test_discussion_includes_the_submitted_domain():
    """A bare HN headline often has no topical words; the domain carries signal."""
    text = embeddings.embedding_text(
        row(
            kind="discussion",
            title="Show HN: my weekend project",
            metadata=json.dumps({"outbound_url": "https://www.arxiv.org/abs/1234"}),
        )
    )
    assert "arxiv.org" in text


def test_repo_uses_release_notes():
    text = embeddings.embedding_text(
        row(kind="repo", title="o/r v1", body="Adds CUDA graph support.")
    )
    assert "CUDA graph" in text


def test_text_is_capped():
    text = embeddings.embedding_text(row(title="t", summary="x" * 5000))
    assert len(text) <= 2000


def test_missing_fields_do_not_produce_stray_whitespace():
    assert embeddings.embedding_text(row(title="Only a title")) == "Only a title"


def test_pending_selects_unembedded_and_stale_items(conn, source_id):
    def add(external_id, content_hash, embedded_hash):
        conn.execute(
            "INSERT INTO items (source_id, external_id, kind, url, title, "
            "content_hash, embedded_hash) VALUES (?, ?, 'article', 'https://e.test', 't', ?, ?)",
            (source_id, external_id, content_hash, embedded_hash),
        )

    add("fresh", "h1", None)      # never embedded
    add("stale", "h2", "old")     # text changed since embedding
    add("current", "h3", "h3")    # up to date

    assert {r["id"] for r in embeddings.pending(conn)} == {
        r["id"] for r in conn.execute(
            "SELECT id FROM items WHERE external_id IN ('fresh', 'stale')"
        )
    }


def test_store_marks_items_embedded_at_their_current_hash(conn, source_id):
    conn.execute(
        "INSERT INTO items (source_id, external_id, kind, url, title, content_hash) "
        "VALUES (?, 'a', 'article', 'https://e.test', 't', 'hash-1')",
        (source_id,),
    )
    rows = embeddings.pending(conn)
    embeddings.store(conn, rows, [[0.0] * embeddings.DIMENSION])

    assert embeddings.pending(conn) == []
    stored = conn.execute("SELECT COUNT(*) c FROM item_vectors").fetchone()["c"]
    assert stored == 1


def test_store_replaces_rather_than_duplicates_a_vector(conn, source_id):
    conn.execute(
        "INSERT INTO items (source_id, external_id, kind, url, title, content_hash) "
        "VALUES (?, 'a', 'article', 'https://e.test', 't', 'hash-1')",
        (source_id,),
    )
    embeddings.store(conn, embeddings.pending(conn), [[0.0] * embeddings.DIMENSION])
    conn.execute("UPDATE items SET content_hash = 'hash-2'")
    embeddings.store(conn, embeddings.pending(conn), [[1.0] + [0.0] * (embeddings.DIMENSION - 1)])

    assert conn.execute("SELECT COUNT(*) c FROM item_vectors").fetchone()["c"] == 1


def test_mismatched_vector_count_is_caught():
    with pytest.raises(ValueError):
        embeddings.store(None, [row()], [])  # strict=True on zip


def test_items_without_a_content_hash_are_not_re_embedded_forever(conn, source_id):
    """Rows predating the content_hash column must still settle after one pass.

    Marking them with NULL would be indistinguishable from "never embedded",
    so every scheduled run would re-embed the whole legacy backlog.
    """
    conn.execute(
        "INSERT INTO items (source_id, external_id, kind, url, title, content_hash) "
        "VALUES (?, 'legacy', 'article', 'https://e.test', 't', NULL)",
        (source_id,),
    )
    rows = embeddings.pending(conn)
    assert len(rows) == 1

    embeddings.store(conn, rows, [[0.0] * embeddings.DIMENSION])
    assert embeddings.pending(conn) == []

    # A later fetch that gives the row a real hash re-embeds it exactly once.
    conn.execute("UPDATE items SET content_hash = 'real-hash'")
    assert len(embeddings.pending(conn)) == 1
