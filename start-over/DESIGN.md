# Design

How Tributary looks and feels, in words. The owner liked this design in an
earlier prototype. It is a **starting point to beat, not a template**: keep
what works, and change anything that a better idea improves.

## Feel

- **Phone first.** One column about 430px wide, centred on bigger screens,
  with a 16px side margin. Screens swap in place, and **sheets** slide up over
  them for anything secondary: settings, a story's details, adding a topic.
- **Image-led and fast to scan**, like a social app's feed, with none of its
  hooks: no autoplay, no endless loading (a **Show more** button after about
  fifty cards), and **"You're all caught up"** with a tick at the end of
  what is new.
- **Chrome is waste.** Big cards are wanted; bars, borders and labels earn
  their place or go.

## Look

- **A river palette.** A sage-tinted pale ground (about `#f1f4f1`), white
  surfaces, deep green-black ink (`#14211d`), muted grey-green secondary text,
  a current-green accent (`#23735f`) for buttons and links, and **one warm
  signal colour** (orange, `#e0773a`) used only for "new". A full dark theme
  mirrors it.
- **Two typefaces**: a characterful grotesque for headings and the wordmark
  (Bricolage Grotesque, heavy weights), and a friendly sans for body text
  (Figtree).
- **Round shapes.** Pill buttons, cards with about 18px corners, sheets with
  rounded top corners.
- **Every kind has a colour** (article, paper, video, discussion, release), so
  a card with no picture still has a cover: the kind's colour, the kind's name
  in small capitals, and the headline large over it. Never an empty grey box.

## Pieces

- **Story card**: a cover, either the article's own picture with a dark
  gradient under the headline, or the kind's colour. Under it, one line with a
  dot when new, the source in bold and the age ("3h"), then a two-line
  summary, then chips for the reader's topics it belongs to. A card already
  read is dimmed.
- **Tiles**: a two-column grid of tall tiles (4:5), each with a picture or
  colour, a large initial behind it, the name in heavy type, a "new" pill and
  the latest headline. For an overview of several topics.
- **Circles**: a sideways row of round topic faces, ringed in the signal
  colour while they hold something new, with a count under them. A dashed
  circle at the end adds a topic.
- **A layout switch** (a small pill with icons) changes the same stories
  between cards and tiles, the way a profile switches between grid and list.
  It is a choice of view, never a different tab.
- **Source row**: a tick, the source's name, a line of facts (items a week, or
  a warning in the signal colour), and its preview, its latest three
  headlines, each a dash and a line.
- **The example list** in topic creation uses the story card in a compact
  form, with ✓ and ✗ beside each.

## Navigation

- **A topic opens like a profile**: a hero with its name and what it is about,
  **✓ Following** or **Follow**, then its stories.
- **Crumbs** above the title climb up to its parent topic. **Back climbs one
  level**, never all the way home.
- **Related** is a short row on a topic's page, never in the feed. Opening one
  is looking, not following.
- **Settings are quiet.** After a topic is made, its sources sit behind a
  settings entry, each removable in a tap, with a search to add more.
- **The graph**: an interactive map of the reader's topics, their subtopics,
  the sources feeding each and related topics. It has coloured nodes by kind,
  curved links, and dashed links for "related". It is laid out by forces, can
  be dragged and pinched on a phone, keeps names readable while zooming, and
  turns a name that would overlap another into a dot until you zoom in.
  Tapping a node lights up its links, fades the rest and opens a panel with
  what is closest to it. Calm and roomy, not a hairball.

## "New" and reading

- **New means unread and under 48 hours old.** Older unread stories stay in
  the feed to scroll to; they just stop counting.
- **Reading the feed marks what you read**: a card counts as read once it has
  been on screen and then scrolled away over the top, or when you reach "You're
  all caught up" below it. A card never shown is never marked. What was new
  when the list opened stays in place, dimmed, instead of jumping while you
  look.
- These are read marks only. They never feed the ranking.
- **No service worker.** A stale page or feed is worse than an honest error.
