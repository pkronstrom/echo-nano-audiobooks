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
