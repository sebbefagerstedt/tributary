-- Small key/value table for facts about the database itself. First use: the
-- embedding model and dimension, so switching models is caught loudly instead
-- of silently comparing vectors from two different spaces.
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- The content hash an item was embedded at. Differing from items.content_hash
-- means the text changed and the vector is stale.
ALTER TABLE items ADD COLUMN embedded_hash TEXT;

CREATE INDEX idx_items_embed_pending ON items(id) WHERE embedded_hash IS NULL;
