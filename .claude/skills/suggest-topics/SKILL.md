---
name: suggest-topics
description: Propose new topics for the Tributary feed by reading what clustered in the last few days, then add the accepted ones to config.toml. Run this daily. Use when the user asks for topic suggestions, says the feed is missing a subject, asks what people are talking about this week, or invokes /suggest-topics.
---

# Suggesting topics

Tributary labels stories by scoring them against topic descriptions in
`config.toml`. Finding what clusters is automated; **naming it is not**, because
the pipeline deliberately runs with no API key. This skill is the naming step:
you read what clustered and propose what to call it. The user accepts or rejects.

Nothing here writes to the database. The only file you change is `config.toml`,
and only after the user has said yes to specific topics.

## 1. Get the groups

```
uv run trib topics --suggest --days 7
```

Each group prints its size, how many of its stories **no current topic claims**,
which topics already cover it, and up to eight headlines.

If the database is missing (a cloud session has the repo but not
`tributary.db`, which is gitignored and lives in the Actions cache), say so
rather than guessing — the user should run this where the database is, or you
can read `https://sebbefagerstedt.github.io/tributary/data.json`, which carries
the last 120 stories with their titles, summaries and current topics. Say which
of the two you used.

## 2. Read, then propose

Work from the headlines, not the group numbers. For each group worth naming:

- **Skip groups that are already covered.** A group whose `unclaimed` count is
  low is being handled by the existing spine. The interesting groups are the
  ones sorted to the top, with stories nothing claims.
- **Propose at most three or four topics per day.** A spine that grows every day
  stops being a spine. If nothing is genuinely uncovered, say so and stop —
  that is a good outcome, not a failed run.
- **Name it what a reader would call it**, not what the cluster is technically
  about. "Running it yourself" beats "local inference optimisation".

For each proposal give the user:

```
slug         short-kebab-case
name         what appears on the filter chip
description  one sentence describing the KIND OF STORY that belongs here
why          the headlines that made you propose it, quoted
```

The description is the part that does the work. It is embedded and compared
against each story by cosine similarity, so it must read like a sentence
describing a kind of story — the existing entries in `config.toml` are the
model. **Keywords do not work here.** "quantization, GGUF, llama.cpp" scores
badly; "running models locally: quantization, inference speed and GPU
requirements" scores well.

## 3. Check it against the spine before offering

Read the current `[topics]` section of `config.toml` first. Reject your own
proposal if:

- An existing description already covers it. Overlap is allowed — a story takes
  every topic it clears, up to `max_per_story` — but two topics that mean the
  same thing split the same stories for no benefit.
- It names one event rather than a kind of story. "The Hugging Face outage" is a
  *story*, and the clusterer already groups those. A topic should still make
  sense next month.
- It names one company or model. Those are **entities**, a layer that does not
  exist yet (see "Topics as an ontology" in `NEXT.md`). Do not smuggle them in
  as topics — say that it would be better as an entity and move on.

## 4. Apply what the user accepts

Add each accepted topic to `config.toml` as a `[[topics.spine]]` entry, matching
the surrounding style. Then tell the user, in one line:

> Adding a topic changes the spine fingerprint, so the next `trib run` re-labels
> every story, not just new ones. Takes a few seconds.

Offer `uv run trib topics` to apply it immediately, and `uv run trib topics
--stats` to see where the stories landed. A topic that takes almost everything
is worded too broadly; one that takes nothing is too narrow or is not something
the sources cover.

Do not commit. The user decides when their config is worth a commit.
