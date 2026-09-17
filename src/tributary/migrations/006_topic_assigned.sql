-- Records that a story has been through topic assignment. A separate marker for
-- the same reason `enriched` is one: matching no topic is a valid outcome, and
-- without this every off-spine story would be rescored on every run.
CREATE TABLE topic_assigned (
    story_id INTEGER PRIMARY KEY REFERENCES stories(id) ON DELETE CASCADE,
    at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Stories are filtered by topic, so the lookup runs the other way round too.
CREATE INDEX story_topics_by_topic ON story_topics (topic_id, story_id);
