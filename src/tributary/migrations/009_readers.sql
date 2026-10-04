-- Readers: the redesign's profiles and their own topics (VISION.md).
--
-- A profile is a name and nothing else -- no password yet. Each profile owns
-- topics, and each topic names the sources that feed it. A source a reader
-- added is fetched like any other, while some topic uses it; `origin` keeps the
-- config sync from switching it off for not being in config.toml.
ALTER TABLE sources ADD COLUMN origin TEXT NOT NULL DEFAULT 'config';  -- config|reader

CREATE TABLE profiles (
    id         INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL UNIQUE,
    layout     TEXT    NOT NULL DEFAULT 'grid',      -- grid|cards
    onboarded  INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- `key` is the topic's identity within a profile: a spine slug for a topic
-- that started from a starter subject, a slug of its name otherwise.
-- `spine_slug` says which version-1 topic it can borrow placements from;
-- `vector` is its description embedded (int8, base64), for the fit filter on
-- topics the spine does not know.
CREATE TABLE reader_topics (
    id          INTEGER PRIMARY KEY,
    profile_id  INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    key         TEXT    NOT NULL,
    name        TEXT    NOT NULL,
    description TEXT,
    spine_slug  TEXT,
    parent_key  TEXT,
    vector      TEXT,
    muted       TEXT    NOT NULL DEFAULT '[]',        -- JSON list of words
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (profile_id, key)
);

CREATE TABLE reader_topic_sources (
    topic_id  INTEGER NOT NULL REFERENCES reader_topics(id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    PRIMARY KEY (topic_id, source_id)
);

-- Seen is per profile and per story: read in one topic, read everywhere.
CREATE TABLE reader_seen (
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    story_id   INTEGER NOT NULL,
    seen_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (profile_id, story_id)
);
