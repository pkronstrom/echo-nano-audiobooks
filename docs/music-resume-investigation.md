# Music resume separation — offline implementation

The installed book-menu build reopened the current audiobook from Music Playback.
The offline implementation captures a bounded native indexed Music context before
starting a playlist and restores it only when the user selects Music Playback.
No device installation or hardware acceptance is implied.

## Native evidence

- Browser selection calls the playlist hook before `0x0307b0b2`. The native
  continuation then clears configuration offsets `0x68` (milliseconds) and
  `0x6c` (resume flag), performs native teardown, sets state mode `0xf2`, and
  opens the player. Capturing in `playback_begin` would be too late.
- Player entry `0x030827ba` with a null argument resets configuration index
  `0x66` to 1 at `0x030828e4`. Restoring only that field before entry would
  therefore select the wrong track.
- Native queue construction `0x030603d0` takes a global index and recreates
  the raw file entry, directory descriptor, and native queue caches. For a
  saved folder scope, `0x0305e64c` converts its local index to a global index.
- Native save `0x03085000` persists additional library ancestry and cache
  locations. Library restoration at `0x0305591c` reads those flash caches;
  it is not a universal safe shortcut for indexed resume.

## Implemented behavior

The retained context contains scalar settings, a `media_ref`, and milliseconds;
no pointer, open handle, decoder buffer, or opaque player snapshot is retained.
Capture occurs at the shared successful path/selected-M3U launch boundary.
Milliseconds use the live resident player when available, otherwise native
saved resume time.

Supported contexts are native raw indexed mode 99, scopes 2 (folder) and 3
(global), and order 0/1. Music Playback checks the saved raw identity first,
then native player entry reconstructs the queue using the saved global index.
The complete 32-byte native file record (name, attributes, timestamps, size and
cluster), parent and raw index must match both preflight and reconstruction before the saved time
is armed for the normal seek path. Native playback settings are restored.
A changed queue aborts player initialization and leaves Music Playback routing
to Music Library until a deliberate new selection.

Absent, stale, unsupported, or differently selected storage/filesystem contexts
route through the original main-menu Music Library dispatch. They do not clear
the active book or reinterpret its native state as music. Library modes 8/9/10
are intentionally unsupported by this first restoration path. A later playlist
launch while a book is active retains the earlier Music context.

Supported Music dispatch uses native callback removal (`0x03059910`) to stop
the decoder and save the book before opening player window3. The original
Music icon only opens window1 and can reuse a running service, so merely arming
restoration before falling through to that dispatch does not work. The actual
main-menu dispatch/callback/save ordering is covered by an ARM test.

The explicit path launch API uses the existing native browser launch bridge,
including teardown. It consumes a bounded absolute UTF-16 path once and does
not depend on the selected browser node after arming.

## Verification and limits

`tests/test_music_resume_arm.py` contains seventeen ARM checks for capture timing,
actual native player entry and queue construction, saved milliseconds/settings,
folder-index conversion, stale raw identity, changed reconstruction, unsupported
library mode, and main-menu fallback/passthrough. Native count/global-ordinal
cache access and filesystem/device services are intercepted; the native queue
constructor and raw directory enumerators execute real instructions.

This is RAM-lifetime resume; refresh and restart clear it. Native library modes
8/9/10 need a separate validated design. Mode10 enumerates flash media-cache
tables at native `0x0305d6ce`, rather than raw filesystem entries. Previous shuffle history is reconstructed by
native initialization rather than retained. Generic M3U playback still uses the
existing shared `playback_active` classification. Storage identity is the native
selected-device/filesystem plus raw reference checks, not a cryptographic or
volume-serial binding against replacement media with coincidentally identical
metadata. These tests do not establish boot, audio, or hardware safety.
