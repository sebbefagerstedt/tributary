"""The page's lens maths, checked against the numpy that produced its vectors.

`web/index.html` is one file with no build step, so its JavaScript has never had
a test runner. That is survivable for rendering -- a wrong string is visible --
and not survivable for arithmetic: a personal lens decides what the feed holds
by cosine over the int8 centroids `export._centroids` packs, and a sign error in
the decode would simply return the wrong stories, quietly and forever.

So the page marks its lens maths as a pure block, this slices it out verbatim
and runs it under node, and the answers are compared with numpy's. Nothing is
duplicated: the code under test is the code that ships.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess

import numpy as np
import pytest

from tributary import embeddings, export

PAGE = export.WEB_DIR / "index.html"
START, END = "/* LENS_MATHS_START */", "/* LENS_MATHS_END */"

needs_node = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node is not installed; the page's own maths cannot be run",
)


def lens_maths() -> str:
    """The block the page marks as pure, exactly as it ships."""
    text = PAGE.read_text()
    return text[text.index(START) + len(START) : text.index(END)]


def pack(vector: np.ndarray) -> str:
    """A centroid as the bundle carries it: normalised, int8, base64."""
    unit = vector / np.linalg.norm(vector)
    packed = np.clip(np.rint(unit * export.VECTOR_SCALE), -127, 127).astype(np.int8)
    return base64.b64encode(packed.tobytes()).decode("ascii")


def unpack(packed: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(packed), dtype=np.int8).astype(np.float64)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def run_in_node(script: str, payload: dict) -> dict:
    """Run the shipped block plus `script`, and read back what it printed."""
    source = f"{lens_maths()}\nconst input = JSON.parse(process.argv[1]);\n{script}"
    done = subprocess.run(
        ["node", "-e", source, json.dumps(payload)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_the_block_stays_pure():
    """The slice only works because nothing in it touches the page."""
    block = lens_maths()
    for forbidden in ("document.", "localStorage", "window.", "bundle."):
        offenders = [
            line for line in block.splitlines()
            if forbidden in line and not line.strip().startswith(("*", "/*", "//"))
        ]
        assert not offenders, (forbidden, offenders)


@needs_node
def test_the_page_decodes_a_centroid_the_way_numpy_packed_it():
    rng = np.random.default_rng(0)
    packed = [pack(rng.standard_normal(embeddings.DIMENSION)) for _ in range(6)]

    out = run_in_node(
        "console.log(JSON.stringify(input.packed.map((p) => [...decodeVector(p)])));",
        {"packed": packed},
    )
    for got, expected in zip(out, packed, strict=True):
        assert got == list(unpack(expected)), "a byte came back with the wrong sign"


@needs_node
def test_the_pages_cosine_agrees_with_numpy():
    """The number the whole feature turns on."""
    rng = np.random.default_rng(1)
    pairs = [
        (pack(rng.standard_normal(embeddings.DIMENSION)),
         pack(rng.standard_normal(embeddings.DIMENSION)))
        for _ in range(50)
    ]

    got = run_in_node(
        "console.log(JSON.stringify(input.pairs.map(([a, b]) =>"
        " cosine(decodeVector(a), decodeVector(b)))));",
        {"pairs": pairs},
    )
    want = [cosine(unpack(a), unpack(b)) for a, b in pairs]
    assert np.allclose(got, want, atol=1e-12), "the page and numpy disagree about cosine"


@needs_node
def test_a_weighted_mean_folds_earlier_seeds_in_by_their_number():
    """Teaching a lens a fifth story must not weigh it against the other four."""
    rng = np.random.default_rng(2)
    prior = pack(rng.standard_normal(embeddings.DIMENSION))
    fresh = pack(rng.standard_normal(embeddings.DIMENSION))

    got = run_in_node(
        "console.log(JSON.stringify([...meanVector("
        "[decodeVector(input.prior), decodeVector(input.fresh)], input.weights)]));",
        {"prior": prior, "fresh": fresh, "weights": [4, 1]},
    )
    blended = unpack(prior) * 4 + unpack(fresh)
    want = unpack(pack(blended))

    assert np.abs(np.array(got) - want).max() <= 1, "more than a rounding tie apart"
    assert cosine(np.array(got, dtype=float), want) > 0.9999
    # And it really is weighted: four parts prior is nearer the prior.
    assert cosine(np.array(got, dtype=float), unpack(prior)) > cosine(
        np.array(got, dtype=float), unpack(fresh)
    )


@needs_node
def test_a_lens_matches_on_its_words_before_it_has_been_taught_anything():
    """The half that makes an unmeasured vector floor safe: a new lens works."""
    story = {"title": "A scheduler for shared GPUs", "summary": "Tail latency.",
             "source": "Blog", "topics": [], "entities": [], "items": [], "centroid": None}

    got = run_in_node(
        "console.log(JSON.stringify({"
        " hit: lensMatcher({ name: 'Scheduling', terms: ['scheduler'], vector: null })(input.s),"
        " miss: lensMatcher({ name: 'Robotics', terms: ['robotics'], vector: null })(input.s),"
        " named: lensMatcher({ name: 'scheduler', terms: [], vector: null })(input.s),"
        "}));",
        {"s": story},
    )
    assert got == {"hit": True, "miss": False, "named": True}


@needs_node
def test_the_vector_half_cuts_at_the_floor():
    """A story the words miss is caught only when it is close enough."""
    rng = np.random.default_rng(3)
    base = rng.standard_normal(embeddings.DIMENSION)
    near = base + rng.standard_normal(embeddings.DIMENSION) * 0.35
    far = rng.standard_normal(embeddings.DIMENSION)

    story = lambda v: {  # noqa: E731
        "title": "Nothing in common", "summary": "", "source": "",
        "topics": [], "entities": [], "items": [], "centroid": pack(v),
    }
    got = run_in_node(
        "const lens = { name: 'zzzz', terms: ['zzzz'], vector: input.lens };"
        "console.log(JSON.stringify({ floor: LENS_FLOOR,"
        " near: lensMatcher(lens)(input.near), far: lensMatcher(lens)(input.far),"
        " nearCos: cosine(decodeVector(input.lens), decodeVector(input.near.centroid)),"
        " farCos: cosine(decodeVector(input.lens), decodeVector(input.far.centroid)) }));",
        {"lens": pack(base), "near": story(near), "far": story(far)},
    )

    assert got["nearCos"] >= got["floor"] > got["farCos"], got
    assert got["near"] is True and got["far"] is False


# --- booting the whole page --------------------------------------------------
# Syntax and arithmetic are not the same thing as "it runs". The browser surface
# this page touches is small enough to stub in thirty lines, so the script is
# evaluated whole, handed a real exported bundle through a fake `fetch`, and
# then asked whether a lens actually filters the feed. It catches the bug class
# a string assertion never will: a function that was renamed in one place.

DOM_STUB = """
const made = [];
const el = (id) => {
  const node = {
    id, innerHTML: '', textContent: '', value: '', dataset: {},
    style: {}, classList: {
      _on: new Set(),
      toggle(c, force) { if (force === undefined ? this._on.has(c) : !force) this._on.delete(c);
                         else this._on.add(c); },
      add(c) { this._on.add(c); }, remove(c) { this._on.delete(c); },
      contains(c) { return this._on.has(c); },
    },
    addEventListener() {}, removeEventListener() {}, setAttribute() {},
    getAttribute: () => null, querySelector: () => el('q'), querySelectorAll: () => [],
    focus() {}, scrollTo() {}, closest: () => null, appendChild() {}, remove() {},
  };
  made.push(node);
  return node;
};
const nodes = new Map();
global.document = {
  body: el('body'),
  getElementById(id) { if (!nodes.has(id)) nodes.set(id, el(id)); return nodes.get(id); },
  querySelectorAll: () => [], addEventListener() {}, createElement: () => el('new'),
};
const cell = new Map();
global.localStorage = {
  getItem: (k) => (cell.has(k) ? cell.get(k) : null),
  setItem: (k, v) => cell.set(k, String(v)),
  removeItem: (k) => cell.delete(k),
};
global.history = { pushState() {}, back() {}, go() {}, replaceState() {} };
global.navigator = {};
global.window = { matchMedia: () => ({ matches: false }), scrollTo() {},
                  addEventListener() {}, location: { href: '' } };
global.scrollTo = () => {};
global.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve(BUNDLE) });
"""


def boot(bundle: dict, script: str) -> dict:
    """Evaluate the page against a bundle, then run `script` once it has loaded."""
    page = PAGE.read_text()
    body = page[page.index("<script>") + len("<script>") : page.rindex("</script>")]
    source = (
        f"const BUNDLE = {json.dumps(bundle)};\n{DOM_STUB}\n{body}\n"
        "setTimeout(() => { try {\n" + script + "\n} catch (e) {"
        " console.error(e && e.stack || e); process.exit(1); } }, 50);"
    )
    done = subprocess.run(
        ["node", "-e", source], capture_output=True, text=True, timeout=60, check=False
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


@pytest.fixture
def page_bundle(conn, source_id):
    from test_export import seed as seed_stories

    seed_stories(conn, source_id)
    return export.build_bundle(conn)


@needs_node
def test_the_page_boots_and_paints_a_card(page_bundle):
    """Nothing throws on the way up, and a real headline reaches the DOM.

    Trending rather than the feed, because it is the one surface that shows
    everything: these fixtures are clustered but never labelled, so there is no
    topic or entity to follow and an unscoped feed is empty by design.
    """
    out = boot(page_bundle, """
      view = 'trending';
      render();
      const html = document.getElementById('main').innerHTML;
      console.log(JSON.stringify({
        stories: bundle.stories.length,
        shown: visible().length,
        painted: bundle.stories.filter((s) => html.includes(s.title)).length,
        teachable: html.includes('data-seed='),
      }));
    """)
    assert out["stories"] > 0
    assert out["shown"] == out["stories"], "Trending should hold everything"
    assert out["painted"] == out["stories"], "a story was scored but never drawn"
    assert out["teachable"], "a card offers no way to teach a subject from it"


@needs_node
def test_a_lens_named_after_a_word_fills_the_feed_with_it(page_bundle):
    """The whole point, end to end: following nothing, a lens is the feed."""
    out = boot(page_bundle, """
      const target = bundle.stories.find((s) => /paper/i.test(s.title));
      follows.clear();
      forgetLenses();
      const empty = visible().length;
      const lens = createLens('Paper');
      render();
      console.log(JSON.stringify({
        empty,
        followed: [...follows],
        shown: visible().map((s) => s.title),
        wanted: target.title,
      }));
    """)
    assert out["empty"] == 0, "following nothing should be an empty feed"
    assert out["followed"] == [out["followed"][0]] and out["followed"][0].startswith("lens:")
    assert out["wanted"] in out["shown"], out
    assert all("paper" in title.lower() for title in out["shown"]), out["shown"]


@needs_node
def test_teaching_a_lens_pulls_in_a_story_its_words_would_miss(page_bundle):
    """The vector half, through the real page: a story sharing no words with the
    lens's name arrives once the lens has been taught with it."""
    out = boot(page_bundle, """
      follows.clear();
      forgetLenses();
      const lens = createLens('zzzznothingmatchesthis');
      const before = visible().length;
      const teach = bundle.stories.find((s) => s.centroid);
      addSeed(lens, teach.story_id);
      forgetLenses();
      console.log(JSON.stringify({
        before,
        seeds: lens.seeds.length,
        taught: Boolean(lens.vector),
        after: visible().map((s) => s.story_id),
        wanted: teach.story_id,
      }));
    """)
    assert out["before"] == 0, "a lens nothing is named after should match nothing"
    assert out["seeds"] == 1 and out["taught"], "the seed did not reach the vector"
    assert out["wanted"] in out["after"], "the story it was taught with did not come back"


@needs_node
def test_the_digest_offers_a_way_to_make_one_and_then_lists_it(page_bundle):
    """A lens has to be reachable: makeable on the subjects page, and listed
    there afterwards even when it is matching nothing."""
    out = boot(page_bundle, """
      view = 'topics';
      render();
      const before = document.getElementById('main').innerHTML;
      createLens('Quiet subject nothing matches');
      render();
      const after = document.getElementById('main').innerHTML;
      console.log(JSON.stringify({
        offersForm: before.includes('data-new-lens='),
        headed: before.includes('Your own subjects'),
        listed: after.includes('Quiet subject nothing matches'),
        quiet: after.includes('quiet'),
      }));
    """)
    assert out["offersForm"], "no way to name a subject on the subjects page"
    assert out["headed"] and out["listed"], out
    assert out["quiet"], "a lens matching nothing must still say so, not vanish"


@needs_node
def test_a_lens_opens_as_a_subject_and_can_be_thrown_away(page_bundle):
    """Same panel as a topic or a name, plus the two controls only a subject
    you wrote yourself needs: what taught it, and a way to delete it."""
    out = boot(page_bundle, """
      const lens = createLens('Paper');
      fillSubject({ kind: 'lens', id: lens.id });
      const panel = document.getElementById('subject-body').innerHTML;
      const matching = subjectStories({ kind: 'lens', id: lens.id }).length;
      const before = lenses.length;
      removeLens(lens.id);
      console.log(JSON.stringify({
        named: panel.includes('Paper'),
        follow: panel.includes('data-follow="lens:' + lens.id + '"'),
        cards: (panel.match(/<article class="card/g) || []).length,
        matching,
        deletable: panel.includes('data-drop-lens='),
        before,
        after: lenses.length,
        stillFollowed: follows.has('lens:' + lens.id),
      }));
    """)
    assert out["named"] and out["follow"], out
    assert out["matching"] > 0 and out["cards"] == out["matching"], (
        "the panel should show its stories as the feed's own cards", out)
    assert out["deletable"], "a subject you made has no way out"
    assert out["before"] == 1 and out["after"] == 0
    assert not out["stillFollowed"], "deleting left the follow behind"


@needs_node
def test_every_card_has_a_cover_and_its_headline_once(page_bundle):
    """A picture when the story has one, its headline set as the cover when not.

    The typographic cover is what keeps a wall of papers and releases -- which
    never carry art -- as even as a wall of articles. And the headline is the
    cover, so it must not be printed a second time underneath.
    """
    out = boot(page_bundle, """
      bundle.stories[0].media_url = 'https://e.test/art.jpg';
      for (const s of bundle.stories.slice(1)) s.media_url = null;
      const [art, bare] = bundle.stories.map(cardHTML);
      const count = (html, needle) => html.split(needle).length - 1;
      console.log(JSON.stringify({
        artImage: art.includes('class="cover-img"'),
        artType: art.includes('cover-type'),
        bareImage: bare.includes('cover-img'),
        bareType: bare.includes('cover-type'),
        bareTitleOnce: count(bare, bundle.stories[1].title) === 1,
        artTitleOnce: count(art, bundle.stories[0].title) === 1,
      }));
    """)
    assert out["artImage"] and not out["artType"], "a story with art should lead with it"
    assert out["bareType"] and not out["bareImage"], "a story without art needs a cover"
    assert out["bareTitleOnce"] and out["artTitleOnce"], "the headline is printed twice"


@needs_node
def test_a_subject_is_the_place_itself(page_bundle):
    """Its stories are the feed's cards, and nothing sends you off to the feed.

    Asked 2026-09-23: *"It should not need to route to the feed"* -- and the
    parked-story row, which explained arithmetic nobody asked about, is gone.
    """
    out = boot(page_bundle, """
      const agents = { slug: 'coding', name: 'Coding agents', parent: 'agents',
                       parent_name: 'AI agents' };
      bundle.stories[0].topics = [agents];
      bundle.stories[1].topics = [{ slug: 'agents', name: 'AI agents' }];  // parked
      fillSubject({ kind: 'topic', slug: 'agents' });
      const panel = document.getElementById('subject-body').innerHTML;
      console.log(JSON.stringify({
        cards: (panel.match(/<article class="card/g) || []).length,
        seeFeed: panel.includes('data-see-feed'),
        parkedRow: panel.includes('Not under a subtopic'),
        leaf: panel.includes('data-subject="topic:coding"'),
      }));
    """)
    assert out["cards"] == 2, out
    assert not out["seeFeed"], "the panel still routes to the feed"
    assert not out["parkedRow"], out
    assert out["leaf"], "the subtopic should still be listed under its shelf"


@needs_node
def test_the_topics_page_has_a_tile_per_shelf_and_a_ring_per_follow(page_bundle):
    """Explore tiles for what is in the bundle, circles for what you follow --
    including a follow the bundle has nothing for, which still needs a control."""
    out = boot(page_bundle, """
      bundle.stories[0].topics = [{ slug: 'coding', name: 'Coding agents',
                                    parent: 'agents', parent_name: 'AI agents' }];
      bundle.stories[1].topics = [{ slug: 'companies', name: 'Companies & money',
                                    parent: 'industry', parent_name: 'Industry & policy' }];
      follows.clear();
      follows.add('topic:agents');
      follows.add('topic:long-gone');
      view = 'topics';
      render();
      const html = document.getElementById('main').innerHTML;
      console.log(JSON.stringify({
        tiles: (html.match(/class="tile"/g) || []).length,
        rings: (html.match(/class="ring[ "]/g) || []).length,
        quiet: html.includes('data-subject="topic:long-gone"'),
        followFromTile: html.includes('class="tile-follow on" data-follow="topic:agents"'),
      }));
    """)
    assert out["tiles"] == 2, out
    assert out["rings"] == 2 and out["quiet"], "a quiet follow lost its control"
    assert out["followFromTile"], out


@needs_node
def test_a_lens_matches_whole_words_with_either_plural():
    """A lens called "test" filled up with *testimony* (reported 2026-09-23)."""
    cases = [
        ("test", "Congressional testimony", False),
        ("test", "A new test for agents", True),
        ("dog", "Dogs can read", True),
        ("dogs", "A dog story", True),
        ("news", "Newsom signs a bill", False),
        ("claude", "Claude's memory", True),
        ("gpt-5", "GPT-5 is out", True),
    ]
    got = run_in_node(
        "console.log(JSON.stringify(input.cases.map(([term, title]) => matchesWord("
        "{ title, summary: '', source: '', topics: [], entities: [], items: [] }, term))));",
        {"cases": cases},
    )
    assert got == [want for _, _, want in cases]


@needs_node
def test_a_lens_made_inside_a_topic_only_filters_that_topic(page_bundle):
    out = boot(page_bundle, """
      const [a, b] = bundle.stories;
      a.title = 'A paper about coding'; a.topics = [{ slug: 'coding', name: 'Coding agents',
        parent: 'agents', parent_name: 'AI agents' }];
      b.title = 'A paper about chips'; b.topics = [{ slug: 'chips', name: 'Chips' }];
      const anywhere = createLens('paper');
      const inside = createLens('paper', 'agents');
      fillSubject({ kind: 'topic', slug: 'agents' });
      const panel = document.getElementById('subject-body').innerHTML;
      console.log(JSON.stringify({
        anywhere: subjectStories({ kind: 'lens', id: anywhere.id }).map((s) => s.story_id),
        inside: subjectStories({ kind: 'lens', id: inside.id }).map((s) => s.story_id),
        a: a.story_id, b: b.story_id,
        listedHere: panel.includes('data-subject="lens:' + inside.id + '"'),
        otherNotHere: !panel.includes('data-subject="lens:' + anywhere.id + '"'),
        formHere: panel.includes('data-parent="agents"'),
      }));
    """)
    assert out["a"] in out["anywhere"] and out["b"] in out["anywhere"]
    assert out["inside"] == [out["a"]], out
    assert out["listedHere"] and out["otherNotHere"] and out["formHere"], out


@needs_node
def test_stories_in_no_topic_have_a_tile_and_a_panel(page_bundle):
    out = boot(page_bundle, """
      bundle.stories.forEach((s, n) => { s.topics = n ? [{ slug: 'chips', name: 'Chips' }] : []; });
      view = 'topics';
      render();
      const page = document.getElementById('main').innerHTML;
      fillSubject(parseSubject('unsorted:'));
      const panel = document.getElementById('subject-body').innerHTML;
      console.log(JSON.stringify({
        tile: page.includes('data-subject="unsorted:"'),
        cards: (panel.match(/<article class="card/g) || []).length,
        form: panel.includes('data-new-lens'),
      }));
    """)
    assert out == {"tile": True, "cards": 1, "form": True}, out


@needs_node
def test_a_circle_plays_its_new_stories_then_moves_on(page_bundle):
    """Oldest unread first, one at a time, each marked seen as it is shown, and
    past the last one on to the next circle with something new."""
    out = boot(page_bundle, """
      const [a, b] = bundle.stories;
      const c = { ...b, story_id: 999, title: 'A third story, elsewhere', items: [] };
      bundle.stories.push(c);
      a.topics = [{ slug: 'chips', name: 'Chips' }];
      b.topics = [{ slug: 'chips', name: 'Chips' }];
      c.topics = [{ slug: 'rag', name: 'RAG' }];
      a.published_at = '2026-09-20T10:00:00Z'; b.published_at = '2026-09-21T10:00:00Z';
      follows.clear(); follows.add('topic:chips'); follows.add('topic:rag');
      marks.seen.clear();
      openViewer('topic:chips');
      const first = document.getElementById('viewer').innerHTML.includes(a.title);
      const seenFirst = marks.seen.has(a.story_id);
      viewerStep(1);
      const second = document.getElementById('viewer').innerHTML.includes(b.title);
      viewerStep(1);
      console.log(JSON.stringify({
        first, seenFirst, second,
        movedOn: viewer && viewer.queue[viewer.s].key === 'topic:rag',
        third: document.getElementById('viewer').innerHTML.includes(c.title),
        noTimer: !/setTimeout|setInterval/.test(drawViewer.toString()),
      }));
    """)
    assert out["first"] and out["seenFirst"] and out["second"], out
    assert out["movedOn"] and out["third"], out
    assert out["noTimer"], "the viewer must not advance on its own"


@needs_node
def test_the_page_opens_on_topics_and_the_feed_row_is_the_circles_small(page_bundle):
    """Topics is home (2026-09-23), and the Feed's filter row carries every
    subject you follow -- names included, which it used to leave out -- each
    with its picture, lit while something in it is new."""
    out = boot(page_bundle, """
      const opened = view;
      localStorage.setItem(key('view'), 'saved');   // a tab left open last time
      loadProfileState();
      const reopened = view;
      const [a] = bundle.stories;
      a.entities = [{ kind: 'org', name: 'NVIDIA' }];
      a.media_url = 'https://e.test/art.jpg';
      follows.clear(); follows.add('entity:NVIDIA');
      marks.seen.clear();
      view = 'feed';
      render();
      const row = document.getElementById('filters').innerHTML;
      console.log(JSON.stringify({
        opened, reopened,
        name: row.includes('data-filter="entity:NVIDIA"'),
        picture: row.includes('https://e.test/art.jpg'),
        lit: row.includes('class="filter new"'),
      }));
    """)
    assert out["opened"] == "topics" and out["reopened"] == "topics", out
    assert out["name"] and out["picture"] and out["lit"], out
