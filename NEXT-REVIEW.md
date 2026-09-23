# Tributary — NEXT.md review questions

2026-09-23 · prepared for the owner, to go through together. The same content
is in the doc at https://claude.ai/code/artifact/29ff7267-6825-4aa1-b3ea-5ddb9acfacaf,
but **this file is the copy that lives with the code**; if the two ever differ,
ask the owner which one they answered in.

**Delete this file once the review is done and `NEXT.md` has been rewritten.**

## Why this exists

Nine questions decide how `NEXT.md` gets rewritten; nothing in it is removed
until the owner answers them. The file is 449 lines in seven sections, and about
half of it is built or was written against the page before the 2026-09-23
redesign. Every claim was checked against the code, config and workflow.

The proposed new shape, around the owner's two big directions:

1. Start here: this review, deleted once done
2. Multiple users: posting, comments, shared topics, hosting, identity
3. Subjects outside AI: product launches, search by query, GDELT, the popularity bar
4. Ready to start: small, self-contained jobs
5. Needs your decision
6. Designed, deliberately not built
7. Your open asks

That would take it from 449 lines to roughly 200.

## The nine questions

Each has the context behind it and what is recommended. A short answer next to
each is enough.

1. **One "Multiple users" heading?** Posting and comments, shared topics (your
   own subjects, visible to others) and the notes-and-takes idea all need
   accounts and a server.
    - Recommendation: yes, one section. It also carries the unsolved part: a
      comment tied to a story's ID is deleted when stories are rebuilt, so
      comments need an address that survives that.
2. **One "Subjects outside AI" heading?** Product launches, search by query
   (fetching when you search, not only on a schedule), GDELT and the popularity
   bar all belong to that move.
    - Recommendation: yes. `config.toml` line 329 still tells triage to exclude
      consumer gadget reviews, so that line moves too.
3. **TLDR AI: keep or drop?** It needs a special adapter (one daily issue
   carries about ten stories). Its value is the hand-written blurbs.
    - Recommendation: drop, or keep at low priority. The labs are now covered
      directly.
4. **Search inside a topic.** Search is silently limited to the topic you are
   standing in, and "Nothing matches X" does not say so.
    - Options: search everything, or say which topic was searched.
      Recommendation: say which topic, since it keeps the place you chose.
5. **A subtopic under a topic you follow.** Following a topic already covers its
   subtopics in the feed, but a subtopic's tile still shows **+**.
    - Options: show it as covered, or have following a topic stop covering its
      subtopics. Recommendation: show it as covered, since the feed already
      works that way.
6. **Names on a subject's page?** The last idea from the "tabs across a subject"
   survey: show who keeps appearing in a subject (OpenAI, Claude, NVIDIA).
    - Recommendation: yes, as a row of chips under "Under this". It is small and
      uses data the page already has.
7. **Ranking that learns from what you do?** From the old "Phase 5": use your
   saves and dismissals to rank.
    - Flag: this sits right next to the rule that ranking is not an engagement
      metric. Recommendation: rule it out, or allow only explicit signals (saves
      and dismissals), never time spent.
8. **"Verifierad (mer trovärdig)": still wanted?** From the original notebook
   page: the app saying out loud that independent sources agree, not just
   ranking such stories higher.
    - Recommendation: keep as an idea. It needs judging when sources are not
      independent, such as rewrites of one wire story.
9. **OK to drop the items that resolve themselves, and the setup note?**
    - Old stories with outdated item labels leave the 30-day feed by about
      2026-10-17.
    - Stories fetched before 2026-09-22 without pictures leave it by about
      2026-10-22.
    - The dev-machine Chromium note is a setup fix already in `CLAUDE.md`.
    - Recommendation: drop all three.

## Removed or moved without a question

These are built, outdated or duplicated. They are listed so the owner can veto
any of them.

| Entry in `NEXT.md` | Why | Proposed |
| --- | --- | --- |
| Redesign the frontend | Built. It predates Topics as home, the circles, the viewer and the map/reader split, all recorded in `CLAUDE.md`. | Remove |
| Whether topics stay as a filter row | Answered: the owner asked for the row to look cooler, not to go. | Remove |
| Confirm before unfollowing, as X does | Nobody has lost a follow by mis-tapping. | Remove |
| Personal lenses: how the private version works | Built and documented in `CLAUDE.md`. | Remove |
| Personal lenses: the shared version, and the 120-story reach limit | Both need the server. | Move to Multiple users |
| Personal lenses: "your subjects that caught nothing" | Not built. It only needs the page and shows what the sources miss. | Move to Ready to start |
| Spine topic (a person adding a topic to `config.toml`) | Nothing left to build. | Remove |
| Misfiled cyber-misuse story: a "why did it land here" command | Still useful for every misfiled story. | Move to Ready to start |
| Misfiled cyber-misuse story: a security facet | Facets are no longer shown anywhere, so it would change nothing you can see. | Remove |
| GDELT | A source for subjects beyond AI. | Move to Subjects outside AI |
| Phase 6+: multi-user | Duplicates posting and comments. | Remove |
| Phase 5: notes and takes | Overlaps comments. | Move to Multiple users |
| Phase 5: catch-me-up digest | Mostly exists as the circles that play what is unread. | Remove |
| "Blocked on something external" heading | Nothing in it is blocked on anything external. | Remove |

Kept as they are: the posting and commenting design, the Ready to start list
(feed finder, linked URLs, full entity names, patch-release filtering), the
0.72 match threshold to measure, the three "designed, deliberately not built"
ideas, and the owner's ask for only the most popular news.

## After the answers

One rewrite of `NEXT.md`, shown to the owner before it is merged. Answers can
come as comments on the doc, in a chat session, or written next to each
question in this file.

- [ ] Answer the nine questions
- [ ] Veto anything in the table above that should stay
- [ ] Rewrite `NEXT.md` in the new shape, review it, then delete this file
