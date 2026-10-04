"""The redesign's API (`/api/next/...`): profiles, topics, seen and discovery."""

from __future__ import annotations

import numpy as np

from test_api import client  # noqa: F401 - the seeded app fixture
from tributary import embeddings


def fake_embed(monkeypatch):
    def embed(texts, model_name=None):
        out = []
        for _ in texts:
            v = np.zeros(embeddings.DIMENSION, dtype=np.float32)
            v[0] = 1.0
            out.append(v.tolist())
        return out

    monkeypatch.setattr(embeddings, "embed", embed)


def test_a_reader_makes_a_profile_and_a_topic_and_reads(client, monkeypatch):  # noqa: F811
    fake_embed(monkeypatch)
    assert client.get("/api/next/ping").json() == {"ok": True}
    made = client.post("/api/next/profiles", json={"name": "Sebastian"}).json()
    assert made["onboarded"] is False
    assert client.get("/api/next/profiles").json() == {"profiles": ["Sebastian"]}

    topic = client.put(
        "/api/next/profiles/Sebastian/topics/ai-video",
        json={"name": "AI video", "sources": ["Test Feed"], "muted": ["crypto"]},
    ).json()
    assert topic["sources"] == ["Test Feed"] and topic["vector"], "a topic of your own is embedded"

    client.patch("/api/next/profiles/Sebastian", json={"layout": "cards", "onboarded": True})
    client.post("/api/next/profiles/Sebastian/seen", json={"story_ids": [1, 2]})
    got = client.get("/api/next/profiles/Sebastian").json()
    assert got["layout"] == "cards" and got["onboarded"] and got["seen"] == [1, 2]
    assert [t["id"] for t in got["topics"]] == ["ai-video"]

    client.delete("/api/next/profiles/Sebastian/topics/ai-video")
    assert client.get("/api/next/profiles/Sebastian").json()["topics"] == []


def test_mistakes_are_said_plainly(client):  # noqa: F811
    assert client.post("/api/next/profiles", json={"name": " "}).status_code == 400
    assert client.get("/api/next/profiles/Nobody").status_code == 400
    client.post("/api/next/profiles", json={"name": "S"})
    bad = client.put("/api/next/profiles/S/topics/x", json={"name": "X", "sources": ["No such"]})
    assert bad.status_code == 400 and "No source" in bad.json()["detail"]


def test_a_subject_finds_the_known_sources_whose_stories_fit(client, monkeypatch):  # noqa: F811
    fake_embed(monkeypatch)
    body = client.get("/api/next/discover", params={"q": "models"}).json()
    assert body["kind"] == "subject"
    # Whether the fixture's stories fall inside the 30-day window depends on
    # today's date, so only the shape is checked here; test_suggest checks the
    # ranking with stories dated now.
    assert isinstance(body["sources"], list) and body["note"]
