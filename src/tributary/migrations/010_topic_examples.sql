-- A reader's topic can be taught by stories: following one event starts from
-- the story you were reading. `examples` is a JSON list of story ids; when it
-- is not empty, `vector` is their centroids' mean rather than the description.
ALTER TABLE reader_topics ADD COLUMN examples TEXT NOT NULL DEFAULT '[]';
