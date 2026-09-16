-- Records that an item has been through identifier extraction. Needed as a
-- separate marker because "found nothing" is a valid outcome: without it, every
-- item with no identifiers would be rescanned on every run.
CREATE TABLE enriched (
    item_id INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
    at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
