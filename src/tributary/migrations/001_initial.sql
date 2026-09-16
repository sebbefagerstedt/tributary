-- Core schema. Tables for later phases are created now so the shape is fixed
-- early; they simply stay empty until the phase that fills them.

CREATE TABLE sources (
    id              INTEGER PRIMARY KEY,
    kind            TEXT    NOT NULL,          -- rss|hn|arxiv|hf|github|youtube|reddit
    name            TEXT    NOT NULL,
    url             TEXT,
    config          TEXT    NOT NULL DEFAULT '{}',   -- JSON, user-set adapter options
    state           TEXT    NOT NULL DEFAULT '{}',   -- JSON, adapter fetch state (etag, cursors)
    enabled         INTEGER NOT NULL DEFAULT 1,
    last_fetched_at TEXT,
    last_error      TEXT,                      -- NULL when the last fetch succeeded
    last_error_at   TEXT,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (kind, name)
);

-- One row per ingested atom: an article, video, paper, model, repo or comment thread.
CREATE TABLE items (
    id            INTEGER PRIMARY KEY,
    source_id     INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    external_id   TEXT    NOT NULL,            -- stable id within the source
    kind          TEXT    NOT NULL,            -- article|video|paper|model|repo|discussion|post
    url           TEXT    NOT NULL,
    canonical_url TEXT,                        -- normalised; a clustering join key
    title         TEXT    NOT NULL,
    author        TEXT,
    published_at  TEXT,                        -- ISO8601 UTC
    fetched_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    summary       TEXT,                        -- source-provided abstract/description
    body          TEXT,                        -- full text or transcript when available
    media_url     TEXT,                        -- og:image, video thumbnail, paper figure
    metadata      TEXT    NOT NULL DEFAULT '{}',
    triage_state  TEXT    NOT NULL DEFAULT 'pending',  -- pending|kept|rejected
    triage_score  REAL,
    UNIQUE (source_id, external_id)
);
CREATE INDEX idx_items_published  ON items(published_at DESC);
CREATE INDEX idx_items_triage     ON items(triage_state, published_at DESC);
CREATE INDEX idx_items_canonical  ON items(canonical_url) WHERE canonical_url IS NOT NULL;

-- Extracted join keys (arXiv ids, HF slugs, repos, DOIs, outbound links).
-- Tier-1 clustering is a self-join on this table: precise and free.
CREATE TABLE identifiers (
    id      INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    type    TEXT    NOT NULL,   -- arxiv|hf_model|hf_dataset|github_repo|doi|url
    value   TEXT    NOT NULL,
    UNIQUE (item_id, type, value)
);
CREATE INDEX idx_identifiers_lookup ON identifiers(type, value);

CREATE TABLE stories (
    id                    INTEGER PRIMARY KEY,
    title                 TEXT,
    summary               TEXT,
    why_it_matters        TEXT,
    first_seen            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    last_activity         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    materially_updated_at TEXT,   -- advances only on a new primary source; drives resurfacing
    score                 REAL NOT NULL DEFAULT 0,
    synthesized_at        TEXT    -- NULL => needs (re)synthesis
);
CREATE INDEX idx_stories_score ON stories(score DESC, last_activity DESC);

CREATE TABLE story_items (
    story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    item_id  INTEGER NOT NULL REFERENCES items(id)   ON DELETE CASCADE,
    role     TEXT    NOT NULL,   -- seed|coverage|paper|code|video|discussion
    PRIMARY KEY (story_id, item_id)
);
CREATE INDEX idx_story_items_item ON story_items(item_id);

CREATE TABLE entities (
    id      INTEGER PRIMARY KEY,
    kind    TEXT NOT NULL,       -- model|org|person|tool|paper|dataset
    name    TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]',
    UNIQUE (kind, name)
);

CREATE TABLE item_entities (
    item_id   INTEGER NOT NULL REFERENCES items(id)    ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    PRIMARY KEY (item_id, entity_id)
);

CREATE TABLE story_entities (
    story_id  INTEGER NOT NULL REFERENCES stories(id)   ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id)  ON DELETE CASCADE,
    PRIMARY KEY (story_id, entity_id)
);

-- The curated browse spine. Tags/entities below it are derived, not listed here.
CREATE TABLE topics (
    id        INTEGER PRIMARY KEY,
    slug      TEXT NOT NULL UNIQUE,
    name      TEXT NOT NULL,
    parent_id INTEGER REFERENCES topics(id) ON DELETE SET NULL
);

CREATE TABLE story_topics (
    story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    topic_id INTEGER NOT NULL REFERENCES topics(id)  ON DELETE CASCADE,
    PRIMARY KEY (story_id, topic_id)
);

CREATE TABLE follows (
    id          INTEGER PRIMARY KEY,
    target_kind TEXT NOT NULL,   -- topic|entity|source
    target_id   INTEGER NOT NULL,
    weight      REAL NOT NULL DEFAULT 1.0,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (target_kind, target_id)
);

CREATE TABLE interactions (
    id       INTEGER PRIMARY KEY,
    story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    action   TEXT    NOT NULL,   -- seen|opened|saved|dismissed
    at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX idx_interactions_story ON interactions(story_id, action);

-- Your own takes. One user today; the same table becomes posts when there are many.
CREATE TABLE notes (
    id         INTEGER PRIMARY KEY,
    story_id   INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    body       TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Observed spend, so the cost estimate in the plan is measured rather than assumed.
CREATE TABLE llm_usage (
    id            INTEGER PRIMARY KEY,
    at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    route         TEXT NOT NULL,   -- synthesis|transcript|adjudication
    model         TEXT NOT NULL,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    batch         INTEGER NOT NULL DEFAULT 0
);
