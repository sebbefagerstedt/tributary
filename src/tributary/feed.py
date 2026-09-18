"""Stage 6: ranking, and the story view behind it.

Deliberately not an engagement optimiser. The problem being solved is that
existing feeds waste your time, so optimising for dwell time would rebuild the
thing this is meant to replace. The score is recency times relevance, with a
modest bonus for stories that several independent sources bothered to cover.

Titles and summaries come from the best source's own words. Nothing here needs
a model; synthesis, if it is ever added, replaces `title`/`summary` and nothing
else.
"""

from __future__ import annotations

import math
import sqlite3
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime

# How fast a story falls out of the feed. Two days is roughly how long an AI
# story stays worth reading about.
HALF_LIFE_HOURS = 48.0
# Corroboration is worth something, but never enough to outrank relevance.
# Triage scores cluster tightly (roughly 0.60-0.85), so an uncapped multiplier
# would let cluster size decide the whole ordering -- and the biggest clusters
# are often just one paper arriving from two overlapping feeds. The cap keeps
# corroboration a tie-breaker rather than the ranking.
SOURCE_BONUS = 0.12
ROLE_BONUS = 0.08
MAX_CORROBORATION = 1.25

# Volume is not importance. arXiv puts ~150 papers a day into the pipeline while
# a blog puts out one, so a pure recency-times-relevance ranking hands the entire
# feed to arXiv -- 47 of the first 50 cards, measured. These damp each *repeat*
# from a source or kind as the list is built, so a dominant source still leads
# but stops crowding everything else out. Lower means stricter variety.
SOURCE_DECAY = 0.55
KIND_DECAY = 0.80

# Which item speaks for a story, best first. Ordered by what an item *is*, not
# by the role it was given: "seed" falls to whatever article arrived first, so
# ranking by role would let a wire-service rewrite outrank the paper itself.
_KIND_PRIORITY = ["paper", "model", "repo", "video", "article", "post", "discussion"]
_ROLE_PRIORITY = ["seed", "paper", "code", "video", "coverage", "discussion"]


def _lead_rank(member) -> tuple:
    kind = member["kind"]
    role = member["role"]
    return (
        _KIND_PRIORITY.index(kind) if kind in _KIND_PRIORITY else len(_KIND_PRIORITY),
        _ROLE_PRIORITY.index(role) if role in _ROLE_PRIORITY else len(_ROLE_PRIORITY),
        -(member["triage_score"] or 0.0),
    )


@dataclass(slots=True)
class StoryCard:
    story_id: int
    title: str
    summary: str | None
    url: str
    kind: str
    source: str
    published_at: str | None
    score: float
    media_url: str | None = None
    sources: list[str] = field(default_factory=list)
    roles: dict[str, int] = field(default_factory=dict)
    item_count: int = 1
    seen: bool = False

    def signal(self) -> str:
        """The one-line 'there is more here' row under a card."""
        parts = []
        for role, label in (
            ("paper", "paper"),
            ("code", "repo"),
            ("video", "video"),
            ("discussion", "discussion"),
            ("coverage", "article"),
        ):
            count = self.roles.get(role, 0)
            if count:
                parts.append(f"{count} {label}{'s' if count > 1 else ''}")
        if len(self.sources) > 1:
            parts.append(f"{len(self.sources)} sources")
        return " · ".join(parts)


def _age_hours(published_at: str | None, now: datetime) -> float:
    if not published_at:
        return 24 * 365.0
    try:
        stamp = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return 24 * 365.0
    return max((now - stamp.astimezone(UTC)).total_seconds() / 3600.0, 0.0)


def score_story(relevance: float, age_hours: float, sources: int, roles: int) -> float:
    """Recency-decayed relevance, nudged up by independent corroboration."""
    recency = math.exp(-age_hours / HALF_LIFE_HOURS * math.log(2))
    corroboration = min(
        1.0 + SOURCE_BONUS * max(sources - 1, 0) + ROLE_BONUS * max(roles - 1, 0),
        MAX_CORROBORATION,
    )
    return relevance * recency * corroboration


def build(
    conn: sqlite3.Connection,
    limit: int = 30,
    days: int | None = None,
    include_seen: bool = True,
    diversify_feed: bool = True,
    now: datetime | None = None,
    age_from: str = "newest",
) -> list[StoryCard]:
    """Rank stories and return the cards to show.

    `age_from` exists for `renewal` and nothing else. The feed ages a story by
    its *newest* item, so a late arrival restarts its clock -- which is the wake
    working, and is also the one thing that can put a week-old story above a
    fresh one. Ranking the same stories from `"origin"` instead says what the
    feed would look like if it could not, and the difference is the measurement.
    """
    now = now or datetime.now(UTC)

    where = []
    params: list = []
    if days:
        where.append("st.last_activity >= datetime('now', ?)")
        params.append(f"-{int(days)} days")
    if not include_seen:
        where.append(
            "NOT EXISTS (SELECT 1 FROM interactions x "
            "WHERE x.story_id = st.id AND x.action = 'seen')"
        )
    clause = f"WHERE {' AND '.join(where)}" if where else ""

    stories = conn.execute(
        f"""
        SELECT st.id, st.title, st.summary, st.last_activity,
               MAX(i.triage_score)  AS relevance,
               COUNT(DISTINCT i.id) AS item_count,
               COUNT(DISTINCT i.source_id) AS source_count,
               COUNT(DISTINCT si.role)     AS role_count,
               MAX(COALESCE(i.published_at, i.fetched_at)) AS newest,
               MIN(COALESCE(i.published_at, i.fetched_at)) AS origin
          FROM stories st
          JOIN story_items si ON si.story_id = st.id
          JOIN items i        ON i.id = si.item_id
          {clause}
         GROUP BY st.id
        """,
        params,
    ).fetchall()

    ranked = sorted(
        (
            (
                score_story(
                    row["relevance"] or 0.0,
                    _age_hours(row["newest" if age_from == "newest" else "origin"], now),
                    row["source_count"],
                    row["role_count"],
                ),
                row,
            )
            for row in stories
        ),
        key=lambda pair: pair[0],
        reverse=True,
    )
    # Build cards for a generous slice, then pick from those: diversity needs to
    # know each story's source and kind, which only the card carries.
    pool = [_card(conn, row, score) for score, row in ranked[: max(limit * 6, 60)]]
    return diversify(pool, limit) if diversify_feed else pool[:limit]


def diversify(
    cards: list[StoryCard],
    limit: int,
    source_decay: float = SOURCE_DECAY,
    kind_decay: float = KIND_DECAY,
) -> list[StoryCard]:
    """Greedily pick the highest-scoring card, damping repeats as we go.

    Each additional card from an already-represented source or kind is worth
    progressively less, so the feed stays varied without any hard quota: a day
    where arXiv genuinely is the news still leads with arXiv.
    """
    remaining = list(cards)
    picked: list[StoryCard] = []
    source_counts: dict[str, int] = {}
    kind_counts: dict[str, int] = {}

    while remaining and len(picked) < limit:
        best = max(
            remaining,
            key=lambda card: card.score
            * source_decay ** source_counts.get(card.source, 0)
            * kind_decay ** kind_counts.get(card.kind, 0),
        )
        remaining.remove(best)
        picked.append(best)
        source_counts[best.source] = source_counts.get(best.source, 0) + 1
        kind_counts[best.kind] = kind_counts.get(best.kind, 0) + 1
    return picked


@dataclass(slots=True)
class Renewal:
    """One card in the feed, and what a late arrival bought it.

    `shown` is the date on the card -- the lead item's -- while the ranker ages
    the story from `newest`. When those disagree the feed looks unsorted, which
    is the complaint this measures.
    """

    story_id: int
    title: str
    shown: str | None
    origin: str | None
    newest: str | None
    gap_hours: float
    renewed_role: str
    renewed_kind: str
    renewed_source: str
    position: int
    origin_position: int | None  # None: outside the deeper list ranked from origin
    carried: bool  # in the feed only because something arrived late

    @property
    def lift(self) -> float:
        """What the restarted clock multiplies the story's recency by."""
        return 2 ** (self.gap_hours / HALF_LIFE_HOURS)

    @property
    def moved(self) -> int | None:
        """Positions gained over ranking the same story from its origin."""
        return None if self.origin_position is None else self.origin_position - self.position


def renewal(
    conn: sqlite3.Connection,
    limit: int = 30,
    days: int | None = None,
    now: datetime | None = None,
) -> tuple[list[Renewal], dict]:
    """How much of the feed's order comes from late arrivals restarting clocks.

    A story's clock runs from its newest item, so its wake keeps it alive: an
    hour-old write-up makes a three-day-old paper an hour old for ranking. That
    is the intent -- a story is the announcement plus what it set off -- but
    nothing about a late arrival can push a story *down*. Relevance is a MAX
    over items, corroboration only rises, and the clock only gets younger, so
    every joiner is a pure upgrade and a long tail of arrivals could in
    principle keep a story re-surfacing forever.

    Whether that actually happens is a question about the corpus, not the code.
    This ranks the feed both ways -- once as shipped, once with every story aged
    from its oldest item -- and reports the difference, so the answer is measured
    before any constant is touched.
    """
    now = now or datetime.now(UTC)
    live = build(conn, limit=limit, days=days, now=now)
    if not live:
        return [], {"stories": 0, "renewed": 0, "carried": 0, "median_gap": 0.0, "by_role": {}}

    # Ranked deeper than the feed so a story that merely slips down still gets a
    # position to compare against, rather than falling off the end of the list.
    deep = build(conn, limit=max(limit * 3, 60), days=days, now=now, age_from="origin")
    origin_positions = {card.story_id: n for n, card in enumerate(deep, start=1)}

    ends = _story_ends(conn, [card.story_id for card in live])

    rows = []
    for position, card in enumerate(live, start=1):
        oldest, newest = ends[card.story_id]
        gap = max(_age_hours(oldest["stamp"], now) - _age_hours(newest["stamp"], now), 0.0)
        rows.append(
            Renewal(
                story_id=card.story_id,
                title=card.title,
                shown=card.published_at,
                origin=oldest["stamp"],
                newest=newest["stamp"],
                gap_hours=gap,
                renewed_role=newest["role"],
                renewed_kind=newest["kind"],
                renewed_source=newest["source_name"],
                position=position,
                origin_position=(origin := origin_positions.get(card.story_id)),
                # "Would not be in the feed" means outside the feed's own limit,
                # not merely outside the deeper list built to measure against.
                carried=origin is None or origin > limit,
            )
        )

    renewed = [row for row in rows if row.gap_hours >= 1.0]
    by_role: dict[str, int] = {}
    for row in renewed:
        by_role[row.renewed_role] = by_role.get(row.renewed_role, 0) + 1
    summary = {
        "stories": len(rows),
        "renewed": len(renewed),
        "carried": sum(1 for row in rows if row.carried),
        "median_gap": statistics.median([row.gap_hours for row in renewed]) if renewed else 0.0,
        "by_role": by_role,
    }
    return rows, summary


def _story_ends(conn: sqlite3.Connection, story_ids: list[int]) -> dict[int, tuple]:
    """The oldest and newest member of each story, by the stamp ranking uses."""
    placeholders = ",".join("?" * len(story_ids))
    found: dict[int, list] = {}
    for row in conn.execute(
        f"""
        SELECT si.story_id, si.role, i.kind, s.name AS source_name,
               COALESCE(i.published_at, i.fetched_at) AS stamp
          FROM story_items si
          JOIN items i   ON i.id = si.item_id
          JOIN sources s ON s.id = i.source_id
         WHERE si.story_id IN ({placeholders})
         ORDER BY stamp ASC
        """,
        story_ids,
    ):
        found.setdefault(row["story_id"], []).append(row)
    return {story_id: (members[0], members[-1]) for story_id, members in found.items()}


def _card(conn: sqlite3.Connection, story: sqlite3.Row, score: float) -> StoryCard:
    members = conn.execute(
        """
        SELECT si.role, i.title, i.summary, i.url, i.kind, i.media_url,
               i.published_at, i.triage_score, s.name AS source_name
          FROM story_items si
          JOIN items i   ON i.id = si.item_id
          JOIN sources s ON s.id = i.source_id
         WHERE si.story_id = ?
        """,
        (story["id"],),
    ).fetchall()

    lead = min(members, key=_lead_rank)

    roles: dict[str, int] = {}
    for member in members:
        roles[member["role"]] = roles.get(member["role"], 0) + 1

    seen = conn.execute(
        "SELECT 1 FROM interactions WHERE story_id = ? AND action = 'seen' LIMIT 1", (story["id"],)
    ).fetchone()

    return StoryCard(
        story_id=story["id"],
        # Synthesis, when present, speaks for the story; otherwise the lead item does.
        title=story["title"] or lead["title"],
        summary=story["summary"] or _best_summary(members, lead),
        url=lead["url"],
        kind=lead["kind"],
        source=lead["source_name"],
        published_at=lead["published_at"],
        score=score,
        media_url=next((m["media_url"] for m in members if m["media_url"]), None),
        sources=sorted({m["source_name"] for m in members}),
        roles=roles,
        item_count=len(members),
        seen=seen is not None,
    )


def _best_summary(members: list, lead) -> str | None:
    """The most readable summary in the story, preferring the lead's own.

    The same paper can arrive from an API with a clean abstract and from an RSS
    feed with the abstract buried behind boilerplate; take whichever reads better.
    """
    candidates = [lead, *sorted(members, key=_lead_rank)]
    return next((m["summary"] for m in candidates if m["summary"]), None)


def detail(conn: sqlite3.Connection, story_id: int) -> tuple[StoryCard, list[sqlite3.Row]] | None:
    """One story and everything attached to it, for the drill-down view."""
    row = conn.execute(
        """
        SELECT st.id, st.title, st.summary,
               MAX(i.triage_score) AS relevance,
               MAX(COALESCE(i.published_at, i.fetched_at)) AS newest
          FROM stories st
          JOIN story_items si ON si.story_id = st.id
          JOIN items i        ON i.id = si.item_id
         WHERE st.id = ?
         GROUP BY st.id
        """,
        (story_id,),
    ).fetchone()
    if row is None:
        return None

    members = conn.execute(
        """
        SELECT si.role, i.id, i.title, i.url, i.kind, i.summary, i.author,
               i.published_at, i.metadata, s.name AS source_name
          FROM story_items si
          JOIN items i   ON i.id = si.item_id
          JOIN sources s ON s.id = i.source_id
         WHERE si.story_id = ?
         ORDER BY i.published_at ASC
        """,
        (story_id,),
    ).fetchall()
    return _card(conn, row, 0.0), list(members)


def mark_seen(conn: sqlite3.Connection, story_ids: list[int]) -> None:
    """Record that these cards were shown, so `--unseen` can skip them next time."""
    conn.executemany(
        "INSERT INTO interactions (story_id, action) VALUES (?, 'seen')",
        [(story_id,) for story_id in story_ids],
    )
