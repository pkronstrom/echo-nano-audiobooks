# Activity icon review

Open [the self-contained review](icon-review.html) in a browser. It includes the
actual current bitmap inventory, two proposed sets at native and 4× size,
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

## Proposed directions

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
