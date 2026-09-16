-- FLOAT[384] matches BAAI/bge-small-en-v1.5. The dimension is fixed in DDL, so
-- switching to a model of another size needs a new migration; meta.embedding_model
-- makes an accidental mix fail loudly rather than silently compare nonsense.
CREATE VIRTUAL TABLE item_vectors USING vec0(
    item_id   INTEGER PRIMARY KEY,
    embedding FLOAT[384]
);
