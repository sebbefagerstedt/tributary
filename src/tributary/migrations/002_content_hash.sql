-- Feeds that send no ETag/Last-Modified are re-parsed in full on every poll.
-- Without a content fingerprint every row looks "updated" each time, which
-- churns the database and makes the update signal meaningless downstream --
-- where materially_updated_at decides whether a story resurfaces in the feed.
ALTER TABLE items ADD COLUMN content_hash TEXT;
