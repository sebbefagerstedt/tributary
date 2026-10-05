"""Write public/dev-data.json: a bundle shaped like `trib export`'s, for local
development of the new frontend when no real database is at hand.

The spine and the source names come from the real config.toml, so topics and
sources look as they will; the stories are synthetic and say so in their titles.
Run from the repo root: `uv run python web-next/scripts/make_dev_data.py`.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from tributary.config import load
from tributary.readers import pack

ROOT = Path(__file__).resolve().parents[2]
KIND_BY_SOURCE = {"arxiv": "paper", "hn": "discussion", "github": "repo", "hf": "model"}

cfg = load(ROOT / "config.toml")
rng = random.Random(7)
now = datetime.now(UTC)
leaves = cfg.topics.leaves()
names = {t.slug: t.name for t in cfg.topics.spine}
sources = [s for s in cfg.sources if s.enabled]

# Synthetic vectors shaped like the real ones: a leaf near its shelf, a few
# leaves leaning towards one on another shelf, and each story near its leaf --
# so the tree's related links have something to find.
vrng = np.random.default_rng(7)
DIM = 384
node_vec: dict[str, np.ndarray] = {}


def vec(slug: str) -> np.ndarray:
    # Each topic near the one above it, so a branch points one way.
    if slug not in node_vec:
        parent = next((t.parent for t in cfg.topics.spine if t.slug == slug), None)
        node_vec[slug] = (vec(parent) * 0.8 if parent else 0) + vrng.normal(size=DIM)
    return node_vec[slug]


leaf_vec = {leaf.slug: vec(leaf.slug) for leaf in leaves}
for leaf in rng.sample(leaves, k=len(leaves) // 3):
    other = rng.choice(leaves)
    leaf_vec[leaf.slug] = leaf_vec[leaf.slug] + leaf_vec[other.slug] * 0.9

stories = []
for n in range(480):
    leaf = rng.choice(leaves)
    src = rng.choice(sources)
    kind = KIND_BY_SOURCE.get(src.kind, "article")
    hours = rng.random() ** 1.6 * 24 * 30
    at = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    others = rng.sample(sources, k=rng.choice([0, 0, 0, 1, 2]))
    items = [src, *[o for o in others if o is not src]]
    title = f"{leaf.name}: sample story {n + 1} from {src.name}"
    label = {"slug": leaf.slug, "name": leaf.name}
    if leaf.parent:
        label |= {"parent": leaf.parent, "parent_name": names[leaf.parent],
                  "path": cfg.topics.ancestors(leaf.slug)[::-1]}
    stories.append({
        "story_id": n + 1,
        "title": title,
        "summary": (
            "Synthetic story for developing the new page. "
            "The real site reads the pipeline's data.json."
        ),
        "url": f"https://example.com/{n + 1}",
        "kind": kind,
        "source": src.name,
        "sources": len(items),
        "published_at": at,
        "last_activity": at,
        "score": round(rng.random(), 4),
        "item_count": len(items),
        "media_url": None,
        "centroid": pack(leaf_vec[leaf.slug] + vrng.normal(size=DIM) * 0.9),
        "topics": [label],
        "entities": [],
        "engagement": None,
        "items": [
            {"role": "seed" if i == 0 else "coverage",
             "kind": KIND_BY_SOURCE.get(s.kind, "article"),
             "title": title if i == 0 else f"Coverage of story {n + 1} from {s.name}",
             "url": f"https://example.com/{n + 1}/{i}", "author": None, "source": s.name,
             "published_at": at, "summary": None, "engagement": None}
            for i, s in enumerate(items)
        ],
    })
stories.sort(key=lambda s: s["published_at"], reverse=True)

has_children = {t.parent for t in cfg.topics.spine if t.parent}
bundle = {
    "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "status": {
        "stories": len(stories),
        "newest_item": stories[0]["published_at"],
        "broken_sources": [],
    },
    "facets": [],
    "spine": [
        {"slug": t.slug, "name": t.name, "parent": t.parent,
         "parent_name": names.get(t.parent) if t.parent else None,
         "description": t.description if t.slug in has_children else None}
        for t in cfg.topics.spine
    ],
    "vectors": {"encoding": "int8", "dimension": 384, "scale": 127},
    "stories": stories,
}
out = ROOT / "web-next" / "public" / "dev-data.json"
out.write_text(json.dumps(bundle, separators=(",", ":")))
print(f"wrote {out} with {len(stories)} stories")
