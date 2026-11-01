# Lessons

What an earlier prototype learned by building and measuring, so none of it is
researched again. Each lesson is a fact or a rule, without the code it came
from.

## Finding a site's feed

The reader pastes a site; the app finds its feed. Try in this order, cheapest
and most reliable first:

1. **The page's own `<link rel="alternate">`** with type
   `application/rss+xml`, `application/atom+xml` or `application/feed+json`.
   This is the site saying where its feed is, and it is what Google's own
   Follow button reads.
2. **The well-known paths** publishing tools use: `/feed/`, `/feed`, `/rss/`,
   `/rss`, `/feed.xml`, `/index.xml`, `/rss.xml`, `/atom.xml` (WordPress,
   Ghost, Hugo and the rest). Try both `/feed/` and `/feed`: hosts differ.
3. **A news sitemap**, for a site with no feed: one named in `robots.txt`, or
   at `/sitemap-news.xml`, `/news-sitemap.xml` or `/sitemap_news.xml`. It holds
   the publisher's last 48 hours, under 1000 URLs, dated by
   `news:publication_date`.

**Fetch and parse every candidate before offering it.** A path answering 200
with a web page is not a feed, and that happens (Cohere's `/blog/rss.xml`
served a web page). **A site that refuses to answer is reported as
unreachable**, never as "has no feed".

**A site with no feed and no news sitemap** can be read from its ordinary
sitemap, filtered to one path (for example only `/news/`). Visit each new URL
once for its `<meta>` tags, and never crawl the back catalogue. A sitemap's
`lastmod` is often just the build date, so do not trust it as a publish date.

## Reading feeds

- **Bad XML is rarely why a feed fails.** feedparser recovers from bare
  ampersands, undeclared entities, control characters, leading junk and
  truncation. **Zero entries means the body was never a feed**: a bot check
  page, a JSON error, the wrong encoding or nothing at all. The parser's
  message is the same for all four, so report the content type, size and
  first bytes instead. An empty but valid feed is a success.
- **Fetch politely and cheaply.** Send a descriptive User-Agent, and keep each
  feed's `ETag` and `Last-Modified` to send back as `If-None-Match` and
  `If-Modified-Since`, so an unchanged feed is a 304 with no body. Hash
  each entry's content so a re-parse of the same entry writes nothing.
- **Fetching is idempotent**: an item is keyed on (source, the entry's own
  id). Some feeds re-deliver years-old entries every run, so **drop items
  older than the retention window at fetch** rather than storing and pruning
  them.
- **One source failing never stops a run.** Store the error on the source,
  show it in the topic's settings, and carry on.
- **Keep a summary's links before flattening it to text.** They are what step
  4's suggestions (the sites a source links to most) are made from. Use the
  summary's links, not a full article's: a full article links everything it
  mentions.

## Describing an item, and its picture

- An item that arrives as a bare title gets its words from the linked page's
  `<meta>` description (`og:description`, then `twitter:description`, then
  the plain `description`, which is often site-wide). **Read meta
  tags only, never the page body.** Picking prose out of cookie banners is the
  part of scraping that keeps going wrong.
- **The picture comes from the same pass**: `og:image` (then `twitter:image`),
  resolved against the page's URL. Anything that does not come out as an
  http(s) URL, such as a `data:` URI, is dropped rather than guessed at.
- **Only articles and blog posts are worth a visit for a picture.** A
  publisher maintains `og:image` because every social platform renders its
  link from it. Papers, releases and model cards are not written that way.
  arXiv's `og:image` is its logo on every paper, and GitHub's is a rendered
  image of the release's own title. Refuse both as art.
- Feeds carry pictures in `media:content`, `media:thumbnail` and image
  enclosures. Look there first.

## Sources that behave differently

- **Substack blocks cloud IPs.** It returned 403 on every run from a cloud
  runner while working from a home connection. A server is a cloud IP, so
  Substack feeds will not work there.
- **Reddit needs no API key.** Its `.rss` endpoints are public Atom, given a
  descriptive User-Agent (a default one gets a 403 page), `www.reddit.com`
  (`old.reddit.com/.rss` redirects to a login), and one combined request for
  several subreddits, `r/a+b+c/.rss`, because separate requests use up each
  other's rate limit.
- **Bluesky** has a feed per profile at `bsky.app/profile/<handle>/rss`, but
  no topic or search feeds.
- **Some sites block their own feed path** and serve the same feed through a
  mirror (MarkTechPost's `/feed/` returned 403; its FeedBurner mirror worked).
- **Not worth it:** TikTok has no feed; X is pay-per-read; Discord and Slack
  need a bot per server.
- **Google News RSS is a trap.** Since 2024 every article link in it is an
  encoded redirect that resolves only through an undocumented internal Google
  endpoint, so the real URL, the most useful key for telling two articles
  apart, is lost.
- **GDELT** (open, keyless, every 15 minutes, all world news, with images)
  would work in principle, but it answered HTTP 429 to the first request
  tried, and it is query-driven. Verify before building on it.
- **A digest feed** (one entry per issue, ten unrelated links in it) is not one
  item. Read as one, it averages ten subjects into one vector. Either split it
  into one item per link, or skip it.

## Embeddings

- **Local and free.** A small sentence-embedding model run with ONNX on the
  server's CPU is fast enough for this. The prototype used bge-small-en-v1.5,
  with 384 dimensions. This plan wants a **multilingual** model from the
  start, so every value below has to be measured again on it.
- **Unrelated text scores near 0.5** with bge-style models, so the usable
  similarity range is about 0.5–1.0, and the scores for matches and near
  misses overlap. There is rarely a clean gap to cut at. Prefer **comparing**
  (which of these fits best) over a fixed **threshold**, and measure any
  threshold on labelled examples before trusting it.
- **Short posts score low whatever they are about.** A one-line launch
  headline scored 0.56 against its own topic. Words matter most for short
  items, meaning for long ones.
- **A group of items is scored through its centroid**: the mean of the
  members' vectors, normalised again.
- **Quantising vectors to int8** costs about 0.003 in cosine on average
  (worst 0.011). That is fine for ranking and filtering, and not precise
  enough for a decision made on a 0.02 margin.
- **A topic taught by examples** takes the mean of its examples' vectors.
  For one event, a strict bar was used (about 0.82, unmeasured); a general
  subject wants a looser one (about 0.62, also unmeasured).
- **Match names by name, never by similarity.** A name (a company, a product)
  embeds vaguely. Matching a name needs whole-word rules: a bare "Meta"
  catches "meta-learning", and "Llama" must not match "llama.cpp".
- **Similarity files a story under what it most resembles**, not what it is
  for. An agent paper is also a safety paper and a benchmark paper. Some
  subjects are lexical, and a word pattern finds them far better.

## For later: grouping articles into stories

Not part of the plan yet. These lessons are kept so they are not relearned.

- **Cheapest and most precise first.** First join on a shared strong key: the
  same canonical URL, DOI or paper id. Two posts with the same headline scored
  only 0.888 on embeddings, but shared a link. Only then fall back to
  embedding similarity, within a 14-day window. A key shared by more than
  about eight items is a category, not an event.
- **A wrong merge costs more than a missed link.** On bge-small, 0.92 merged
  85 of 87 true pairs with one false merge in 18,235 hard pairs. Measure it
  again on the new model.
- **Order a feed by when the news broke**, not by the story's last activity.
  Otherwise an old story jumps the queue because someone commented on it.
