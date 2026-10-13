# Activity icon review

Open [the self-contained review](icon-review.html) in a browser. It includes the
actual current bitmap inventory, four revised sets for Settings, Shuffle, Audiobooks and Meditation at native and 4× size,
selected-state previews, individual decisions/comments, local browser saving,
and Copy / Download feedback. The review approves icon artwork only. No icon
substitution or navigation change has been applied to firmware.

The user explicitly requested a reviewable HTML file for icons, with feedback
that can be copied back. Approval remains pending. Audiobooks and Meditation
are prospective activity symbols here, not evidence of existing menu shortcuts.

## Verified stock inventory

Source: stock V1.7.0 `NANOV170.IMG`, SHA-256
`54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116`.
The main menu table is mod21 `0x0300e6d8`, five 8-byte records with the string
ID at offset 6. English labels are decoded from the firmware language section.
The original icon pointer table is mod00 `0x03004124`.

| Order | Exact English label | String ID | Bitmap address |
| --- | --- | --- | --- |
| 1 | File Browser | 0x03 | mod00 0x03072dff |
| 2 | Media Library | 0x58 | mod00 0x03072daf |
| 3 | Music Playback | 0x00 | mod00 0x03072d5f |
| 4 | Music Settings | 0x01 | mod00 0x03072d87 |
| 5 | System Settings | 0xec | mod00 0x03072dd7 |
| 6, existing custom patch | Shuffle | 0x82 | mod21 0x0307951c |

Music Playback is the Now Playing activity. Music Settings and System Settings
are separate activities; collapsing them into one invented stock label would
misrepresent the current interface. The current Shuffle patch uses an S-shaped
symbol, not crossed arrows.

## Format and display constraints

Every main activity bitmap is 20×16 pixels, monochrome, 40 bytes. The bit at
`data[(y // 8) * 20 + x] & (1 << (y % 8))` selects its foreground pixel.
The unaligned renderer at `0x030506d0` confirms the page-major source addressing
and bit order (`0x03050740..0x0305078c`). It clips horizontal coordinates to 128
and vertical coordinates to 32 (`0x030506e6`, `0x03050702`). Thus the active
framebuffer drawing bounds are **128×32**. This is code evidence, not a measurement
of the device's physical display size or a captured device screenshot.

The icon-table renderer at `0x03050868` loads the pointer and explicitly passes
20×16. The main-menu strip uses 25-pixel spacing, e.g. mod21 `0x0307a444` and
`0x0307a45e`; the selection call at `0x0307a46c..0x0307a472` uses x=54 and 20×16.
Selection function `0x03050642` inverts framebuffer bytes with additional edge
adjustments. HTML selected-state previews deliberately show simple inversion;
they are not claimed to reproduce all native border pixels or animation.

`patches/shuffle_10_mod21_cave.S` copies the five pointers and appends its 40-byte
bitmap after the 24-byte table at `0x03079504`. It draws the extra entry outside
the stock five-entry strip loop. Larger resources alone will not produce larger
icons: dimensions, spacing, highlight geometry, animation and clipping must also
change. With only 32 vertical pixels, label space needs deliberate treatment.
This artifact therefore compares icon artwork within the current resource size.

## Round 1 directions (superseded for the four revised icons)

- **A · Crisp:** simplified silhouettes with outlined folder/book, list bars,
  play triangle, audio sliders, system settings shape and crossed Shuffle arrows.
- **B · Heavy:** the same family thickened one horizontal pixel, increasing
  contrast at the expense of internal gaps. Compare at native size, especially
  Books, Meditation and both settings symbols.

A is the starting recommendation, pending the user's recognizability feedback.
Both retain the current 20×16/40-byte constraint. The HTML shows 1× and 4× using
integer-sized SVG pixels; browser zoom and operating-system scaling affect
physical size. No web font or external resource is used. Proposals are editable
pixel constructions, not AI-generated raster images.

## Reproduction

```sh
python3 tools/preview_icons.py
```

The script rejects an unknown stock image, reads the labels and five bitmap
resources directly, and decodes the existing Shuffle assembly bytes. It writes
only the HTML output. The final artifact embeds all pixel data and works offline
without the firmware or Python. Feedback is stored locally where browser policy
allows it; Copy falls back to a selected text field, and Download is also
available. Copy/download is explicit; no feedback is sent automatically.

## Round 2 — 13 October 2026

The user found the first gear too much like a dartboard, asked for stronger
Shuffle arrows and more recognizable books, and could not identify Meditation.
The original feedback is preserved in `reviews/icon-feedback-v1.json`.

[Review v2](icon-review-v2.html) compares four alternatives side by side:

- **A Practical:** open wrench, heavy crossed arrows, closed hardback, seated person.
- **B Classic:** projecting eight-tooth gear, stepped arrows, open book, lotus.
- **C Audio:** crossed tools, solid arrows, book with headphones, guided listening headphones.
- **D Quiet:** horizontal wrench, tight crossing arrows, stacked books, candle.

All remain 20×16 pixels. Choices can be mixed per icon. The other four activities
retain their round-1 alternatives and pending decisions in a separate section.
V2 uses a separate browser-storage key, preserves the previous comments visibly
and in exported feedback, and does not treat a preference as artwork approval.
`icon-review.html` also points to the current revision. The existing firmware
and release ZIP are unchanged. The source generator uses `icon_proposals.py`
and `icon_review_template.html`; the generated review still works as one file.

## Round 3 — variants for all eight activities

The user requested further alternatives for every activity, sharper play tips,
crisper music controls and settings symbols that do not suggest clipped tools,
stars or crossed bones. Their v2 feedback is preserved in
`reviews/icon-feedback-v2.json`, including the earlier v1 review.

[Review v3](icon-review-v3.html) contains four variants for each of eight
activities. Shuffle shortens/removes left-hand rails; books remain open spreads;
meditation offers four candles. Prior v2 D Shuffle, B Open Book and D Candle
remain selectable as explicitly identified references, alongside round-1 Crisp
Music Settings. New variants start pending, with a separate v3 browser-storage
key. Nothing has been installed in firmware.

Every new bitmap has a blank one-pixel perimeter. Play tips are explicitly
rasterized to a point. Checks cover all 32 dimensions/perimeters and uniqueness,
plus browser selection, mixed new/prior identities, exact comments, nested
feedback history, storage, inverse mode and desktop layout. The generator now
uses `icon_proposals_v3.py`; v2 drawings remain available for the references.

### Round 4 — focused refinements

Review: `icon-review-v4.html` (also the current `icon-review.html`). Artwork source:
`tools/icon_proposals_v4.py`. User feedback is preserved verbatim in
`docs/reviews/icon-feedback-v3.json`, including earlier rounds.

There are four alternatives each for solid folders, list-style libraries,
softer play wedges, thinner slider knobs, settings, curved books and slimmer
candles. Slider alternatives distinguish one-pixel reductions in height and
width. Candle A reduces the previous body's width from eight to seven pixels.
The approved round-three shuffle D is retained exactly and carried forward as
approved; all other new artwork starts pending. Original firmware icons and
previous directions are visible beside each applicable comparison.

Validation: 29 bitmap dimensions and blank perimeters checked, alternatives
within each activity distinct, retained shuffle compared pixel-for-pixel.
JavaScript syntax and isolated Chrome checks passed for initial approval state,
selection, comment export, full feedback history, local persistence, inverse
preview and desktop overflow. Contact sheet visually inspected. No firmware
resources or navigation were modified.

### Round 5 — approvals retained, corrections isolated

`icon-review-v5.html` contains four rounded outline folder alternatives, two
cogs and two open wrenches, one slider padding correction, and one symmetrical
book. The library C, play B, shuffle D and candle A from round four remain
pixel-identical and approved. Revised artwork starts pending; original File
Browser remains selectable. Round-four feedback and history are stored in
`docs/reviews/icon-feedback-v4.json`.

The fine slider knobs remain 3 × 2 pixels, with three blank columns at each
outer edge. The even-width canvas and odd-width knobs require a one-pixel
difference between the two internal track gaps. The rounded book is mirrored
about the canvas centre, including its page marks and spine.

Validation: preserved bitmap equality, exact book reflection, equal slider
outer margins, blank perimeters, distinct alternatives, Python and JavaScript
syntax, and isolated Chrome checks of carried approvals, original selection,
comments, export, persistence and inverse preview. Contact sheet inspected.
No firmware or navigation changes.

### Round 6 — settings only

`icon-review-v6.html` puts System Settings first. Two circular hubs with eight
short rectangular teeth offer different weights. The upright wrench has exact
left/right symmetry; the horizontal wrench has exact top/bottom symmetry and
an open mouth facing away from its shaft. Both use two-pixel shafts.

The other seven choices from round five are preserved pixel-for-pixel and
carried forward as approved. Settings remains pending. User feedback is saved
in `docs/reviews/icon-feedback-v5.json`, including the earlier review history.

Validation: bitmap equality for all retained icons, symmetry assertions,
perimeter checks, distinct settings alternatives, JavaScript syntax and
isolated Chrome checks of carried approvals, selection, feedback export,
persistence and inversion. Contact sheet visually inspected. Reordered groups
use current-icon availability (not list position) for the keep-current option.
No firmware or navigation changes.

### Existing libraries — round 1

Following the request to use existing artwork, `icon-library-review.html`
(and the current `icon-review.html`) compares six libraries with eight icons
per library: Bootstrap, Lucide, Tabler, Remix Icon, Pixelarticons and Phosphor.
The six settings cogs appear first, followed by complete sets. Whole-set and
individual selections can be mixed and exported as JSON. All eight approvals
from round six remain the default until replaced. That review is saved in
`docs/reviews/icon-feedback-v6.json`.

The original SVG files and full licences are in `docs/icon-library-assets/`.
Its manifest records exact repository revisions and source paths. The review
embeds all SVGs and licence texts, and works offline. Links open the pinned
upstream source. `python3 tools/build_icon_library_review.py` rebuilds the page.
Source geometry is unchanged; only the display colour is white. This is an
existing-artwork comparison, not another custom-drawn icon round.

Each source viewBox is scaled to 16 × 16, centred in a 20 × 16 canvas, and
thresholded at alpha 128 for the automatic monochrome preview. These browser
rasters are illustrative, not final firmware resources. Feedback records the
source SHA-256 and preview pixels. Original vectors are also displayed enlarged
so rasterisation losses remain visible.

Tabler and Remix include candles; Lucide uses the existing Lab candlestick-lit.
Bootstrap, Pixelarticons and Phosphor use explicitly labelled fire substitutes.
Remix uses its own License v1.0; other notices are MIT and Lucide ISC plus its
inherited MIT notices. All original notices are retained. No assets have been
installed in firmware or added to a release bundle.

Validation: all SVGs parse and use only permitted static drawing elements;
48 nonempty 20 × 16 rasters rendered in isolated Chrome. Whole-set selection,
individual mixing, keeping prior approvals, source identity, feedback comments,
local persistence and export were checked. Desktop comparison inspected.

### Compact grid revision

The existing-library review now shows only eight rows of native 20 × 16 icons,
with System Settings first and File Browser second. Each row has the previous
approval followed by the six libraries in manifest order. Click selects one
icon per row. Existing selections and comments survive through the same local
storage key. Icon-only copy and download controls export the feedback; labels
remain available to assistive technology and on hover. Original SVGs, source
metadata and full licence notices remain embedded, without visible panels.

Checked in isolated Chrome: eight rows, 56 options, exact 20 × 16 CSS-pixel
artwork, one selection per row, click updates, persistence and export. Grid
screenshot inspected. No firmware changes.

### Music-note alternatives

The screenshot selection from 2026-10-13 at 10.58.03 is recorded in
`docs/reviews/icon-feedback-grid-screenshot.json`: Tabler settings, folder, list
and play; Bootstrap sliders; Lucide shuffle; previous book and candle.
The Music row now offers six existing note icons from the same pinned sources.
The first option retains the selected Tabler play triangle. New notes are not
implicitly approved. A fresh storage key preserves the preceding review, and
new-page defaults reflect the screenshot. Source geometry and licences remain
unchanged. Browser checks cover defaults, retained play identity, note selection,
source identity, nonempty bitmap and saved feedback. Grid visually inspected.
