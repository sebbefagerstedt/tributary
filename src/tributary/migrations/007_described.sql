-- Records that an item has been through description fetching. A separate marker
-- for the same reason `enriched` is one: "there was nothing usable to fetch" is
-- a valid outcome, and without this every undescribable item would be retried on
-- every run, forever, over the network.
CREATE TABLE described (
    item_id INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
    at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
