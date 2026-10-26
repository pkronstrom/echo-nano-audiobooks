# Bookmark feedback: offline implementation evidence

Bookmark request captures a feedback generation. The player service publishes
success only after the bookmark journal write returns successfully, or failure
after a rejected request/write. Publication and cancellation share one atomic
word: low two bits encode a result, upper bits a session generation. A canceled
session cannot publish an old result into the next book. Duplicate queued
requests leave the original pending request intact.

The native module27 MusicWin service epilogue at `0x0307a860` reaches a guarded
36-byte stub at `0x0307a014`. The stub checks the playback header before calling
the payload, then executes the original stack cleanup, r4 return and register
restore. The UI consumer ignores a nonzero native window-transition return,
requires the exact MusicWin service/paint identities, and waits while a child
window is already present. It creates its own seven-word child window in the
playback payload, never modifies a resident native callback pointer, and draws
“Bookmark saved” or “Bookmark failed” for 150 native ticks (about 1.5 seconds).

The stub replaces these exact adjacent diagnostic strings:
`[INFO] pLongFileName = ` and `[INFO]  %c `. The only identified references are
ADRs at `0x03079e4e` and `0x03079e5c`. No absolute pointers occur in extracted
module code/data. Only their four-byte printf calls at `0x03079e50` and
`0x03079e5e` are disabled. The filename loop is retained because its r5 result
is used afterward. Integration validates all36 bytes and both original calls.

Native APIs verified against stock disassembly:

| Address | Contract used |
| --- | --- |
| `0x03059828` | Create/link child: `(parent, child, init_argument)` |
| `0x03059840` | Destroy/unlink window, invoking uninit |
| `0x0300e6bc` | MusicWin: child,parent,service,key,paint,init,uninit |
| `0x0307a4df`, `0x0307b993` | Expected MusicWin service and paint pointers |
| `0x03052b08` | UTF-16 rectangle renderer: `(rect,text,2,1,NULL)` |
| `0x03067904`, `0x030678e0` | Save/set/restore render state |
| `0x03007d88` | 640-byte native framebuffer |
| `0x030643d8` | Transfer `(0,0,128,31)` |
| `0x0300d144` | Native100Hz tick counter |

The child uses no native MessageBox state or frame stack. It paints after the
parent in the native dispatcher, using the player's render-state pattern. Its
own service destroys its own address on timeout or session cancellation and
posts57. All player display variants check57 before a full repaint. The native
MessageBox cannot be reused unchanged: it posts227 on timeout, and MusicWin
interprets227 as error recovery, including leaving playback or advancing tracks.

The dispatcher calls child uninit before root uninit at
`0x0306b178..0x0306b1aa`, then returns to module loading through
`0x0306b116`, `0x0306b246`, and `0x0306b256`. Thus normal window transitions
unlink payload callbacks before refresh can replace the payload. The entry
stub also has a missing-header stock fallback. This is evidence for the
examined synchronous lifecycle, not a hardware-safety claim.

ARM tests exercise native window creation/destruction and payload callbacks,
save/failure publication, cancellation, busy-child deferral, render ABI,
timeout redraw, and missing-header epilogue fallback. LCD hardware calls and
the actual font rasterizer are substituted in these tests. Physical text
appearance, input responsiveness during the short modal notice, and device
acceptance remain unvalidated; no installation is authorized by this work.

## Hardware feedback — 2026-10-15, packet/menu build

User clarified accelerated crackle was fixed; category menus still take about
2s Audiobooks/3s Meditations and user considers this tolerable. Double Previous
bookmark gesture on Book B showed a black screen for about a second. Whether
confirmation text appeared and bookmark persisted awaits clarification.

feedback.c paint clears all640 framebuffer bytes, renders a confirmation and
transfers the whole128x32 display; popup lasts150 native ticks (~1.5s). This
explains the screen replacement/timing, but does not prove why it looked black.
Existing tests substitute the native font renderer; they cannot establish
visible glyphs. Investigate native rasterization/render state before patching.


## Invisible-text correction — 2026-10-15, offline

Native glyph/raster instruction tests reproduce blank output with logical mode1
(raw mode1): the rasterizer clears ink bits on the already-cleared framebuffer.
The popup now selects logical mode0, yielding raw mode2 and visible set bits.
The native mode setter translates0↔2, so its returned raw previous value must be
restored directly to the mode halfword rather than passed back through the setter.
Font restoration remains through its symmetric setter.

Regression tests execute the real mode setters and glyph/raster path with a
synthetic glyph, including restoration of raw modes0/1/2. The full-screen popup
and150-tick duration remain; this fixes invisible text, not the screen replacement.
Actual display appearance still requires a device check.
