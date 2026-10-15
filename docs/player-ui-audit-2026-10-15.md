# Player and library UI audit — 2026-10-15

Read-only stock instruction audit, followed by this documentation write. No
firmware edits, builds, device operations or execution validation. Source:
`NANOV170.IMG`. Addresses are overlay-qualified; the same addresses have
different meanings in different modules. Byte strings below are file-order.

## Scope and screen identity

The requested Media Library panel is module22 (`MedialibWinService`). Its
resource126 is 30×32 pixels, drawn at (0,0). Module23, the indexed media browser,
also draws this panel and is a plausible interpretation of “Music Playback
menu”. Clarification remains pending. Module27 is Now Playing (`MusicWinInit`),
and its resources103/104 are only 9×11 and 8×9, respectively: do not remove them
on the assumption that they are the same large side panel.

## Module22 geometry candidates

| Address | Stock bytes | Proposed operation |
| --- | --- | --- |
| 0x03079c42 | `d8f7c7fa` | NOP the resource126 draw (`00bf00bf`). |
| 0x03079c22 | `4ff02308` | Shared full/update text left r8=35 to3 (`4ff00308`). |
| 0x03079c26 | `4ff07109` | Shared text right r9=113 to123 (`4ff07b09`). |
| 0x03079c80 | `1f21` | Full redraw highlight x31 to0 (`0021`). |
| 0x03079d5a | `4ff01f01` | Update highlight x31 to0 (`4ff00001`). |
| 0x03079c84 | `d8f7a6fa` | Redirect full selected-row background draw to local tiler. |
| 0x03079d66 | `d8f735fa` | Redirect update selected/unselected background draw to same tiler. |

Both paths use rectangles built from r8/r9, with rows y0/16 and text y2/18.
Native text drawing is 0x03052b08; native resource drawing is 0x030521d4.
Resources17 and127 are 92×16. Merely moving them to x0 leaves the right side
uncleared/unhighlighted. Draw twice at x0 and x32, as the File Browser solution
does, ending at x124. Keep scrollbar calls at 0x03079eb8/0x03079ec2, x124.

Use a module-local tiler, not an unconditional call into the playback payload:
Media Library remains accessible when that payload has been invalidated.
A candidate 36-byte cave is 0x03079e40..0x03079e63, exact contents
`MSG_SCREN_UP MedialibWinService\n` plus four zero bytes. Module22 has one
decoded ADR reference, at 0x03079a58 (`f9a0`), immediately followed by printf
at 0x03079a5a (`f8f7e5f9`, target0x03071e28). Disable that printf before
reclaiming the string; leaving the ADR is harmless if its r0 is not consumed.
No absolute pointer into the cave was found in module22 code/data. This is a
candidate, not a completed whole-image control-flow/reference proof. Adjacent
literal data begins at0x03079e64 and must be preserved.

The tiler needs to preserve resource ID and y across the first native call,
maintain stack alignment, then call again with x32. The 36-byte extent appears
sufficient, but assembled size/ABI and both redraw paths still need tests.

## Module23 candidate, if the user means the indexed list

Resource126 draw: 0x0307a408, stock `d7f7e4fe`. Full row backgrounds are
0x0307a45a/0x0307a46e; update backgrounds are0x0307a5ae/0x0307a5c2.
Both paths also draw entry glyphs through0x0307a4b6/0x0307a60a at x32.
Scrollbar remains x124 at0x0307a6f8/0x0307a702. Full geometry and a local cave
have not been audited for this module; do not apply the module22 patch table.

## Double-click settings route

The incident record already confirms main-button double-click opens native
sound settings. Module27 key handler0x0307bc76 obtains decoded input from
0x03063242. Event0x40000002 routes to0x0307c4f2; when native flag1 is clear,
0x0307c502 writes u16 argument1 and0x0307c50a (`eef7aefe`) calls
0x0306b26a with window10. The service also opens window10/argument1 at
0x0307a51e (`f0f7a4fe`). Do not assume the key call is the only entry route.

Window10 is Systemset, module32. Entry0x03079418 reads the u16 argument into
0x0300e914+2; argument1 also sets byte0x030041da to1. Module32 shares the
0x03079418 overlay execution region with module27 and replaces that code.
Direct callbacks into module27 while settings is active are invalid.

Module32's menu loader0x03067988 is resident. It loads a 58-byte menu record;
module32 uses count at record+14 and item IDs starting at+16. Root initialization
at0x0307955e requests record236. Each depth record uses24 bytes of UI state,
and menu-record buffers use58-byte strides. This establishes a maximum physical
space of21 halfword item IDs per record, NOT permission to append blindly:
actual sound-menu ID/count, localization, per-action dispatch and other array
limits still require decoding. A payload-owned synthetic menu/record with a
guarded module-local entry may avoid altering the shared language resources.

Native return from settings requests Music window3 at0x0307a700 and joins the
window dispatcher at0x0307a854. Other exits go to window0. Thus returning from
the real settings overlay necessarily reloads module27; a same-module return
cannot be assumed. A child window inside module27, analogous to the existing
bookmark-feedback popup, would retain module27, but extending/replacing the
existing settings menu that way is a separate design decision.

## Now Playing speed label: pending layout proof

Module27 paint is0x0307b992 (callback0x0307b993); service identity0x0307a4df
and window structure0x0300e6bc are already guarded by `playback/feedback.c`.
That existing child-popup pattern offers a known lifecycle for transient UI.
Permanent speed text needs both full and incremental paint coverage and must
not overwrite native fields. Bottom-row native icons occupy x1,95,104,115 at
y25, with other fields between. No always-free label rectangle was established
in this audit. Do not label an arbitrary rectangle “safe” yet.

Next checks: clarify the large-panel screen; execute library full/update tiler
tests with payload absent; decode the sound menu record and Back/selection
dispatch; trace overlay load/reset behavior around active speed state; map
player text/time rectangles before choosing a speed label position. Report
effective speed, including unsupported native1x, rather than desired preference.

## Sound-menu resource decoded

Resident loader0x03067988 loads58 bytes from language slot (258-byte stride).
Stock menu236/System Settings has children237,267,272,288,354,376,393,396,404,426.
Menu237/Music Settings has six children238,247,256,262,263,264, matching the
reported loop/EQ/filter/balance/volume/gain list. This establishes the record
to extend conditionally for active audiobooks, rather than altering every
System Settings menu. Loader and event-dispatch bounds still require execution
coverage; resource capacity alone does not prove a seventh action is safe.
