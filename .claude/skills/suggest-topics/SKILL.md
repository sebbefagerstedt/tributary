---
name: suggest-topics
description: Propose new topics and entities for the Tributary feed by reading what clustered and what recurs in the last few days, then add the accepted ones to config.toml. Run this daily. Use when the user asks for topic suggestions, says the feed is missing a subject, asks what people are talking about this week, wants to add a lab or model to follow, or invokes /suggest-topics.
---

# Suggesting topics and entities

Tributary labels a story on three axes, and each is named by a person rather
than by the pipeline, because the pipeline deliberately runs with no API key:

| Axis | Question | How it is matched | Per story |
|---|---|---|---|
| **Topic** | where does it live | embedding, best fit over leaves | exactly one |
| **Entity** | who is it about | name and alias | any number |
| **Facet** | what kind of thing is it | regex | any number |

Finding what clusters and what recurs is automated. **Naming it is not.** This
skill is the naming step: you read the evidence, propose, and the user accepts
or rejects.

Nothing here writes to the database. The only file you change is `config.toml`,
and only after the user has said yes to specific entries.

The reasoning behind all of this — why there is no threshold, why only leaves
are scored, why facets are regexes — is in `CLAUDE.md` under "Labelling: one
home, three axes". Read it once if anything below seems arbitrary.

If the database is missing (a cloud session has the repo but not
`tributary.db`, which is gitignored and lives in the Actions cache), say so
rather than guessing. `https://sebbefagerstedt.github.io/tributary/data.json`
carries the latest stories with their topics, facets and entities, but it is
too thin to find gaps in; the user should run this where the database is.

## 1. Topics: find where a leaf is missing

```
uv run trib topics --suggest --days 7
```

Each group prints its size, how many of its stories are **parked on a shelf**,
how many have no topic at all, and which topics are currently home to them,
followed by up to eight headlines. Groups are sorted by parked + no-topic.

**Parked is the signal.** Every story gets exactly one home: the leaf that fits
it best. When the top two leaves are on the same shelf and too close to call,
the story sits on the shelf itself instead. So a group with many parked stories
means *the shelf fits and none of its leaves does* — which is exactly what a
missing leaf looks like. A group with nothing parked is being handled.

"No topic" is rare by design — it means a story fell below the floor against
every leaf — and a pile of them means the spine is missing a whole shelf.

## 2. Read, then propose

Work from the headlines, not the numbers.

- **Propose a leaf and name its shelf.** Every proposal sits under one of the
  shelves in `config.toml`. If it fits under none of them, say so — that is a
  bigger change, a new shelf, and worth raising as such rather than slipping in.
- **Propose at most three or four per day.** If nothing is genuinely missing,
  say so and stop — that is a good outcome, not a failed run.
- **Name it what a reader would call it**, and name the subject, not a verb.
  "Speed, memory & cost" works; "Making it run faster" makes the reader ask
  what "it" is.

For each proposal give the user:

```
slug         short-kebab-case
shelf        the parent slug it goes under
name         what appears on the filter chip
description  one sentence describing the KIND OF STORY that belongs here
why          the headlines that made you propose it, quoted
```

**The description is the part that does the work.** It is embedded and compared
against each story, so it must read like the stories themselves are written —
the existing leaves in `config.toml` are the model. Keywords do not work:
"quantization, GGUF, llama.cpp" scores badly; "running a model on your own
machine: GPU requirements, laptops and local inference tooling" scores well.

**Topics are allowed to die.** Propose the specific thing that is actually
happening rather than a timeless category. "The Hugging Face outage" is a fine
leaf while people are arguing about it. Proposing is cheap: a badly named leaf
costs one config entry.

## 3. Check it before offering

Read the current `[topics]` section of `config.toml`. Reject your own proposal
if:

- **An existing leaf already means this.** Under one-home assignment this
  matters more than it used to: a new leaf does not *add* a label, it **takes
  stories away from its neighbours**. Two leaves that mean the same thing split
  one subject in half, and both halves read as broken.
- **It is a single story** rather than a run of them. One outage with one report
  is a story, and the clusterer already groups it. The same outage with
  follow-ups and argument is a topic. The test is whether stories keep arriving.
- **It is a name, not a subject.** A lab, a model line, a tool, a person — those
  are **entities** (step 4), not topics. "Astra 6.1 launch" can be a leaf for a
  few weeks; "Astra" is an entity.
- **It cuts across the shelves.** If a subject would honestly belong under half
  the shelves at once — agents, benchmarks, open source, code — it is a
  **facet**, not a topic. Similarity cannot separate those from their
  neighbours, because a paper really is about all of them at once. Facets are
  regexes in `[[facets]]`; propose one only when a word reliably marks the
  subject, and test the pattern against a few headlines before offering it.

## 4. Entities: names that recur

```
uv run trib entities --suggest
```

This lists proper nouns that recur across recent stories and are not seeded yet,
each with the headlines it came from. It reads summaries rather than titles,
because in a Title Case headline every word looks like a name.

**Expect about half of these to be wrong, and reject them without ceremony.**
Eponyms (`Gaussian`, `Markov`, `Bayesian`), method names (`LoRA`), and the names
of sources (`MarkTechPost`) pass every test the extractor has. The rest are the
point: model lines and products that the seeded list has not caught up with.

For each one worth keeping, propose:

```
kind     model | org | person | tool | paper | dataset
name     the canonical name
aliases  other spellings people use, if any
why      the headlines it came from
```

**Keep names and aliases unambiguous.** Matching is by word, case-insensitive,
so a bare `Meta` would claim every mention of meta-learning, and a bare `Flash`
would claim every story mentioning flash attention. Qualify it: `Gemini Flash`,
`DeepSeek Flash`. If there is no unambiguous way to name it, say so and leave it
out.

To see what the current entities are catching, run `uv run trib entities`. One
naming almost nothing is either misspelt or not something the sources cover.

## 5. Apply what the user accepts

Add accepted leaves as `[[topics.spine]]` entries with a `parent`, accepted
entities as `[[entities]]`, and accepted facets as `[[facets]]` — each in its
own section of `config.toml`, matching the surrounding style. Then tell the
user, in one line:

> Any change to topics, entities or facets changes the label fingerprint, so the
> next `trib run` re-labels every story, not just new ones. Takes a few seconds.

Offer `uv run trib topics` to apply it immediately and show where stories
landed. A new leaf that takes almost everything from its shelf is worded too
broadly; one that takes nothing is too narrow or not something the sources
cover. Either way, the neighbours it took stories *from* are worth a look.

## 6. Notice what has gone quiet, and leave it alone

Run this every time, even when proposing nothing:

```
uv run trib topics --stats
```

The `last story` column says which topics have gone quiet. **Report them; do not
propose deleting them.**

- **It already costs nothing.** The filter row is built from the stories
  actually loaded, so a quiet topic is invisible on the page without anyone
  doing anything.
- **It comes back for free.** If the subject returns, a topic still in the spine
  picks the new stories up. One that was deleted has to be noticed and written
  again.
- **Deleting is not free.** It changes the fingerprint and re-labels the corpus,
  and under one-home it hands the deleted topic's stories to its neighbours —
  which can make a perfectly good neighbour suddenly look swollen.

Thin leaves are also expected while the feed is paper-heavy: `Regulation &
courts` and `Frontier model releases` fill when news does, not before.

**Removing is for entries that were wrong, not ones that are finished.** Say so
when one is genuinely a mistake — it never matched anything, it swallows its
whole shelf, or it duplicates another entry — and offer to remove that. "Quiet
for three weeks" is not a mistake.

Do not commit. The user decides when their config is worth a commit.
