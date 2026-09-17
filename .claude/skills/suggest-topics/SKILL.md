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
- **Propose at most three or four topics per day.** If nothing is genuinely
  uncovered, say so and stop — that is a good outcome, not a failed run.
- **Name it what a reader would call it**, not what the cluster is technically
  about. "Running it yourself" beats "local inference optimisation".

**Topics are allowed to die.** They are not a permanent taxonomy. A topic that
matters for three weeks and then goes quiet has done its job, so propose the
specific thing that is actually happening rather than a timeless category that
will still be true next year and tells the reader nothing. "The Hugging Face
outage" is a fine topic while people are arguing about it. Retiring is step 5.

This is why proposing is cheap: a topic that turns out badly named or too narrow
costs one config line and disappears at the next retirement pass. Do not agonise.

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
- It describes a **single story** rather than a run of them. One outage with one
  report is a story and the clusterer already groups it. The same outage with
  argument, follow-ups and a postmortem is a topic. The test is whether stories
  keep arriving, not whether the subject is timeless.
- It is a **long-lived thing you would follow rather than read about** — a
  company, a lab, a model line. Those are entities, a layer that does not exist
  yet (see "Topics as an ontology" in `NEXT.md`). Mention it and move on. Note
  the line is blurry now that topics can be short-lived: "Astra 6.1 launch" is a
  reasonable topic, "Astra" is an entity.

## 4. Apply what the user accepts

Add each accepted topic to `config.toml` as a `[[topics.spine]]` entry, matching
the surrounding style. Then tell the user, in one line:

> Adding a topic changes the spine fingerprint, so the next `trib run` re-labels
> every story, not just new ones. Takes a few seconds.

Offer `uv run trib topics` to apply it immediately, and `uv run trib topics
--stats` to see where the stories landed. A topic that takes almost everything
is worded too broadly; one that takes nothing is too narrow or is not something
the sources cover.

## 5. Notice what has gone quiet, and leave it alone

Run this every time, even when proposing nothing:

```
uv run trib topics --stats
```

The `last story` column says which topics have gone quiet. **Report them; do not
propose deleting them.** A topic dying means nobody looks at it any more, not
that it should be removed:

- **It already costs nothing.** The filter row is built from the stories
  actually loaded, so a topic with nothing recent is invisible on the page
  without anyone doing anything.
- **It comes back for free.** If the subject returns, a topic still in the spine
  picks the new stories up. One that was deleted has to be noticed and written
  again.
- **Deleting is not free.** Removing an entry changes the spine fingerprint,
  which drops every row in `story_topics` and re-labels the whole corpus. The
  surviving topics are re-derived so nothing is permanently lost, but the
  deleted topic's history goes, and it is pointless churn for a topic that was
  already invisible.

So a long tail of dormant topics is the expected steady state, not a mess to
clean up. The config file grows slowly; that is fine, it is a text file.

**Removing is for topics that were wrong, not topics that are finished.** Say so
when one is genuinely a mistake — it never matched anything, it is worded so
broadly it swallows the feed, or it duplicates another entry — and offer to
remove that. "Quiet for three weeks" is not a mistake.

Do not commit. The user decides when their config is worth a commit.
