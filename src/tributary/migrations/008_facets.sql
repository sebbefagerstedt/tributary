-- Facets: what a story is, as opposed to where it lives.
--
-- Stored by slug rather than by a foreign key into a `facets` table, because a
-- facet has no identity beyond its name and its pattern -- both live in the
-- config, and a change to either re-runs the whole match anyway. A row here is
-- a match, nothing more.
CREATE TABLE story_facets (
    story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    slug     TEXT    NOT NULL,
    PRIMARY KEY (story_id, slug)
);

CREATE INDEX idx_story_facets_slug ON story_facets (slug);
