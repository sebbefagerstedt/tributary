"""Stage 6b: entities.

Who a story is about. A new model is its lab *and* its model line *and* a
frontier release -- three different questions, and only the last one is a topic.
Without this axis the other two get forced into the topic spine, which is what
made topics read as strange: `OpenAI` is not a place you browse, it is something
you follow.

Matched by name and alias, never by similarity. These are proper nouns, and
recognising one does not need a model -- which also means this axis cannot drift
when the embedding does. `identity.py` already extracts the machine-readable
half (arXiv ids, hub repos, GitHub repos) for clustering; this is the half a
reader would recognise.

Seeded entities come from the config. Everything else is proposed for a human to
accept, which is the same rule topics follow and the reason the namespace does
not fill with junk.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field

from tributary.config import EntityConfig
from tributary.db import transaction
from tributary.facets import story_texts


@dataclass(slots=True)
class EntityResult:
    stories: int = 0
    matched: int = 0  # stories carrying at least one entity
    by_entity: dict[str, int] = field(default_factory=dict)


def sync(conn: sqlite3.Connection, seeded: list[EntityConfig]) -> dict[str, int]:
    """Make the entities table hold the seeded list, and return name -> id.

    Accepted entities that came from extraction are left alone: this only owns
    the rows it seeded, so a human's decision is never overwritten by a config
    edit.
    """
    with transaction(conn):
        for entity in seeded:
            conn.execute(
                "INSERT INTO entities (kind, name, aliases) VALUES (?, ?, ?) "
                "ON CONFLICT (kind, name) DO UPDATE SET aliases = excluded.aliases",
                (entity.kind, entity.name, json.dumps(entity.aliases)),
            )
        return {
            f"{row['kind']}:{row['name']}": row["id"]
            for row in conn.execute("SELECT id, kind, name FROM entities")
        }


def _pattern(entity: EntityConfig) -> re.Pattern:
    """One pattern per entity, covering its name and every alias.

    Word-bounded so `Phi` does not match `philosophy`, and longest-first so
    `GPT-4o` is preferred over `GPT` when both would fit. A dot followed by more
    word counts as part of the word, which is what stops the Llama *model*
    matching `llama.cpp` -- a different project, and a tool rather than a model
    -- while still matching "Llama." at the end of a sentence.
    """
    names = sorted(entity.names(), key=len, reverse=True)
    return re.compile(
        r"(?<!\w)(?<!\w\.)(?:" + "|".join(re.escape(n) for n in names) + r")(?!\w|\.\w)",
        re.IGNORECASE,
    )


def run(conn: sqlite3.Connection, seeded: list[EntityConfig]) -> EntityResult:
    """Attach every seeded entity to the stories that name it."""
    result = EntityResult()
    ids = sync(conn, seeded)
    with transaction(conn):
        conn.execute("DELETE FROM story_entities")
        if not seeded:
            return result

        patterns = [(f"{e.kind}:{e.name}", _pattern(e)) for e in seeded]
        for story_id, text in story_texts(conn):
            result.stories += 1
            hit = False
            for key, pattern in patterns:
                if pattern.search(text):
                    conn.execute(
                        "INSERT OR IGNORE INTO story_entities (story_id, entity_id) "
                        "VALUES (?, ?)",
                        (story_id, ids[key]),
                    )
                    result.by_entity[key] = result.by_entity.get(key, 0) + 1
                    hit = True
            result.matched += hit
    return result


def for_stories(conn: sqlite3.Connection, story_ids: list[int]) -> dict[int, list[dict]]:
    """Entity names and kinds per story, for the bundle."""
    if not story_ids:
        return {}
    placeholders = ",".join("?" * len(story_ids))
    found: dict[int, list[dict]] = {}
    for row in conn.execute(
        f"""
        SELECT se.story_id, e.kind, e.name
          FROM story_entities se
          JOIN entities e ON e.id = se.entity_id
         WHERE se.story_id IN ({placeholders})
         ORDER BY e.name
        """,
        story_ids,
    ):
        found.setdefault(row["story_id"], []).append(
            {"kind": row["kind"], "name": row["name"]}
        )
    return found


# --- proposing ---------------------------------------------------------------

# A capitalised run, allowing the digits, dots and hyphens that model names use:
# `Astra`, `DeepSeek`, `GPT-5.6`, `Qwen3.8`.
_PROPER = re.compile(r"[A-Z][A-Za-z0-9]*(?:[.\-][A-Za-z0-9]+)*")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_EDGES = "()[]{}\"'“”‘’,:;!?"

# arXiv summaries open with "Abstract:" and carry "Announce Type:"; the rest are
# words that are capitalised for grammatical reasons rather than being names.
_NOT_NAMES = frozenset(
    {"abstract", "announce", "type", "tags", "however", "english", "chinese", "we", "our"}
)


@dataclass(slots=True)
class Candidate:
    """A proper noun nobody has seeded yet, for a human to accept or reject."""

    name: str
    stories: int
    titles: list[str] = field(default_factory=list)


def _is_concept(word: str) -> bool:
    """`LLM`, `LLMs`, `LLM-based`: acronyms for ideas, not names of things."""
    base = word.split("-")[0]
    if base.endswith("s") and base[:-1].isupper():
        base = base[:-1]
    return base.isupper() and not any(ch.isdigit() for ch in base)


def suggest(
    conn: sqlite3.Connection,
    seeded: list[EntityConfig],
    days: int = 14,
    min_stories: int = 3,
    limit: int = 15,
) -> list[Candidate]:
    """Proper nouns that recur across recent stories and are not seeded yet.

    Read from summaries, not titles, because headlines are Title Case and every
    word in them looks like a name. In prose, a capital letter away from the
    start of a sentence means something -- and a word that is *also* written in
    lower case elsewhere is an ordinary word that happened to be capitalised,
    which is the test that separates `Astra` from `Learning`.

    This is deliberately a proposal, not a decision. Eponyms like `Gaussian`
    pass every test here and are not entities; a human rejects them in a second,
    and nothing becomes followable until someone has said yes.
    """
    known = [_pattern(entity) for entity in seeded]
    capital: dict[str, int] = {}
    lower: dict[str, int] = {}
    found: dict[str, set[int]] = {}
    titles: dict[str, list[str]] = {}

    for row in conn.execute(
        """
        SELECT si.story_id, i.title, i.summary
          FROM stories st
          JOIN story_items si ON si.story_id = st.id
          JOIN items i ON i.id = si.item_id
         WHERE st.last_activity >= datetime('now', ?)
        """,
        (f"-{int(days)} days",),
    ):
        title = row["title"] or ""
        here = set(_PROPER.findall(title))
        for sentence in _SENTENCE.split(row["summary"] or ""):
            for position, raw in enumerate(sentence.split()):
                word = raw.strip(_EDGES)
                if not word:
                    continue
                if position > 0 and _PROPER.fullmatch(word):
                    capital[word] = capital.get(word, 0) + 1
                    here.add(word)
                elif word.islower():
                    lower[word] = lower.get(word, 0) + 1
        for word in here:
            found.setdefault(word, set()).add(row["story_id"])
            examples = titles.setdefault(word, [])
            if title and title not in examples and len(examples) < 2:
                examples.append(title)

    candidates = []
    for word, count in capital.items():
        stories = len(found.get(word, ()))
        if len(word) < 3 or stories < min_stories:
            continue
        if word.lower() in _NOT_NAMES or _is_concept(word):
            continue
        # Written in lower case a quarter as often as capitalised: an ordinary word.
        if lower.get(word.lower(), 0) > count / 4:
            continue
        if any(pattern.search(word) for pattern in known):
            continue
        candidates.append(Candidate(name=word, stories=stories, titles=titles.get(word, [])))

    candidates.sort(key=lambda c: (-c.stories, c.name))
    return candidates[:limit]


def stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every entity with how many stories name it, busiest first."""
    return conn.execute(
        """
        SELECT e.kind, e.name, COUNT(se.story_id) AS stories
          FROM entities e
          LEFT JOIN story_entities se ON se.entity_id = e.id
         GROUP BY e.id
         ORDER BY stories DESC, e.name
        """
    ).fetchall()
