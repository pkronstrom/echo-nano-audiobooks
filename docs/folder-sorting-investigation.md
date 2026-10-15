# Native folder sorting remains unfinished

User reports Hemi-Sync meditation entries show CD2-3 beforeCD1-1. Current natural
sorting exists only in tools/prepare_book.py when generating a new playlist.
Existing playlists are preserved. Native Music/meditation folder listings still
use physical directory order; no claim of natural folder sorting is warranted.

Read-only native audit: module31 enumerator0x03079592 streams first/next through
0x0305dce0/0x0305dcb4 and0x0305d668. It selects raw directory/audio ordinals before
loading names via FAT0x0305e388 or exFAT0x0305d520. Mode3 increments raw index at
0x0305d6b8..c0. Module40 cfw_cmp sorts indexed music metadata, not this browser.

Selection0x0307ad1c..3a derives audio ordinal from page/selection/folder count.
playback/navigation.c install_root computes Back positions from physical order.
Sorting labels alone would corrupt selection identity. A real solution must
maintain ordered-to-raw entry mappings for enumeration, selection and Back.
Playback sequencing is separate: the browser overlay disappears during playback.
A browser ordering fix must at least preserve selected-file native ordinal.

Current playback payload has16B static headroom. A bounded mapping needs audited
browser-overlay storage and explicit overflow behavior. Repeated scans could
avoid persistent storage but risk slow navigation. No new filesystem-order
rewrite, firmware sorting patch, or SD modification was performed. Prepared
M3U playlists are the existing way to get natural playback order; they do not
sort the ordinary browser UI.
