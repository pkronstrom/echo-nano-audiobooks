# Small speed label beside SD (offline follow-up)

The user requested moving the speed label off the title to the middle row,
immediately left of the SD indicator, using the small bottom-row digit size.
The title and bottom controls retain their stock geometry.

## Drawing and ownership

The artist rectangle is stock `(12,12,107,23)`. Its right edge becomes86 only
(exclusive: the artist covers through85) when the guarded ENP2 payload is valid and `playback_active` is true. Ordinary
Music retains107. The width hook moves from title `0x0307ad34` to artist
`0x0307ade8` (expected bytes `6b20adf83c00`, stack rectangle right at+60).
The continuation is `0x0307adee`. The title's stock127 edge is restored by
omitting its old hook.

The paint hook moves from title `0x0307ad72` to artist `0x0307ae22`, preserving
its call to native marquee update `0x03052fe4` before the guarded label draw.
Native artist function `0x0307adc8` reaches this update both on full redraw
(event482 set) and incremental redraw. Both existing callers remain covered.
The same validated module27 LRC diagnostic caves at `0x0307a2c8` (36B) and
`0x0307a39c` (56B) are reused; their original printf suppression remains.
There are no new resident hooks or payload-loader calls.

The label clears only columns86..107, rows12..23. Its ink occupies rows16..23,
right aligned in this region. Columns108..127, including the SD indicator,
all title pixels, and all bottom-row pixels are preserved. Five fixed bitmaps
replace the old label on every draw, including when a shorter rate follows a
longer one. Drawing still requests native display flush flag6.

## Small glyph evidence

Native text glyph generation at `0x03064850..0x03064866` selects12px for font1
and16px otherwise; choosing a smaller rectangle would not create an8px font.
The bottom count renderer `0x0307a96c` uses image resources33..42, with digit
widths from `0x0307ad7c` (digit1 is3px, other digits5px), at y24.

The speed bitmaps copy the exact8px resource canvases for digits1/2/5/7
(resources34/35/38/40). Their16-bit source pixel zero means lit: native
`0x03052270..0x03052282` sets the framebuffer bit for zero and clears it
otherwise. Decimal and x are small matching glyphs in the same8px canvas.
No global text mode or font state is changed, and no additional native image
renderer stack frame is needed.

## Verification and limits

`tests/test_player_speed_label_arm.py`:6 isolated ARM tests passed before the exclusive-boundary follow-up; a seventh
combined-image regression now checks installed patch bytes and executes the
actual payload through the native artist route. They execute
both native full and incremental artist routes, validate width fallback and
unchanged title/bottom instructions, compare all five rendered rates against
the stock image digit resources, check every unaffected framebuffer byte,
check mode/font state preservation, and verify longer-label removal.

Isolated object size is194B, zero BSS, versus172B previously:22B increase within
the prior32B static margin (combined build29 reports16B remaining).
No memory boundary was expanded. No device installation or staging was
performed for this relocation; emulator checks do not establish hardware
appearance or boot safety.


## Offline small speed label — 2026-10-15

20261029 moves actual speed beside SD on the artist row, using native bottom-row
8px digit shapes. Full title width and all bottom controls are preserved. Artist
exclusive rightedge86 meets labelclear86..107 without stale boundary pixels.
394 tests passed in228.285s; scoped independent re-review approved. Payload
24112text+32176BSS leaves16B static margin; boundaries unchanged.
Archive: builds/phase4f-controls-20261015/small-label-reviewed/manifest.json.
Custom SHA256: b5630159bccf08f26632d8000da68a130f60c65bf56e0d29bd96e4d02abb48a3
Recovery20261030 SHA256: 21d22f3b7b7e54920826c487c51f5d6e37ab2cc4c298cf256dd426e9a2d21e32
No device staging performed. Installed20261027 reached menu after userrestart
and Ichigo live speed works; initial startup anomaly remains unresolved.
