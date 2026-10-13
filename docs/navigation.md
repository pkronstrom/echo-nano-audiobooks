# Navigation follow-up

The current test image preserves File Browser hierarchy, direct meditation-file
selection and existing buttons. Books are entered through their M3U in File
Browser. This route is implemented and covered by ARM tests; dedicated
Audiobooks and Meditations shortcuts are not yet implemented.

## What the native firmware permits

The File Browser is window 9. Its launch argument has four bytes: filter,
saved ordinal and a flag. It has no folder-path argument. Main-menu routing at
`0x03079c0e..0x03079c2c` and Media Library Folder Navigation routing at
`0x0307981e..0x03079836` both open it through `0x0306b26a`.

Initialization at `0x030799c4` resets the path to the storage root, initializes
ancestry with `0x030798ce`, and resolves an ordinal via `0x03079794`. Folder
descent `0x0307ad40..0x0307ae46` creates 56-byte ancestry records including
FAT/exFAT descriptors. The depth at browser state `0x03005f6c + 0x1cc`, saved
per-level selections and current two-node selection all participate in Back
navigation and the new audiobook path reconstruction.

Consequently a new label pointing at the existing launch function would merely
open the root; it would not be a useful folder shortcut. A correct shortcut must
establish complete ancestry for its target and preserve native Back behavior.
The existing M3U file resolver does not do that.

## Proposed next implementation

Use empty `.audiobook` and `.meditation` marker files in collection roots,
following the user's 2026-10-13 proposal. Folder names and nested structure can
remain arbitrary. A marker classifies the root and its descendants; individual
books or meditation sessions do not each need another marker. Treat marked
content as excluded from Music, extending the existing `.nomusic` behaviour.

Only show a content shortcut when the mounted card contains a matching marked
root. Recompute availability on a library rescan/card change. If a root vanishes
between discovery and activation, cancel activation safely and refresh the
menu; do not silently send the user to the storage root. Zero matching roots
means no corresponding menu item; one opens that root; multiple roots should
open a chooser of those roots. Discover roots once during scanning rather than
walking the card on every menu redraw.

This is the intended design, not implemented firmware behaviour. Marker
classification, discovery/cache invalidation and dynamic menu routing require
implementation and tests together with the native folder-descent work below.

Main-screen growth is a larger change: the current six-entry table ends directly
before cursor state at `0x0300e708`. More entries require relocating it and
changing count/dispatch, strip drawing and selection geometry. Even the smaller
Media Library route needs coordinated table/restore-cave placement (current
table `0x0300e708`, restore code `0x0300e744`).

Before enabling a shortcut, add native ARM tests for initialization, nested
FAT/exFAT descent, Back through each ancestor, missing-root hiding, multiple-root selection and book
launch after traversal. These ABIs have been mapped but that implementation and
its tests are outstanding. Tomorrow's P3a image retains the existing verified
entry path so the core playback/resume device test can proceed independently.

The separate [icon review](icon-review.html) approves artwork only; it does not
approve or silently enable these navigation changes.
