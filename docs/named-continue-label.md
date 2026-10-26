# Named audiobook Continue row

The Audiobooks landing row now reads `Continue <book name>`. It uses the saved
playlist filename without `.m3u`; generic `BOOK.M3U` uses its immediate parent
folder name. The second row remains Browse books. Name case and Unicode are
preserved; the 256-unit native UTF-16 buffer is bounded and truncation does not
leave a dangling high surrogate.

Formatting uses the already cached, validated last-book path. It adds no disk
reads or extra title buffer. Last-book selection still lasts only for the
current payload lifetime; this change does not make it durable across resets.

To fit the unchanged resident RAM boundary, the last-book identity stores only
the four fields it already checked, and menu ASCII-to-UTF-16 formatting is
shared. Preview journal metadata joins the existing parser/snapshot union:
parsing and journal display have separate lifetimes, and the recursion guard
stays outside the saved snapshot. The snapshot is invalidated before parsing
and its metadata reset afterward, including failed scans. Cold path helpers
share generated code. Audio buffers and DSP processing are unchanged.

Candidate 20261112 / recovery 20261113. All 488 tests passed in 384.249s, plus 34 final focused checks.
Parent review and full build/test evidence are archived in
`builds/phase4i-named-continue-20261016/reviewed/manifest.json`.
No new independent review or device installation has been performed.
Resident text25864+BSS30440 fills the56304-byte static reservation exactly;
its upper boundary and reboot marker are unchanged.


## Superseding offline implementation — 2026-10-18

Candidate 20261120 adds durable selection hints to the existing RSM journal and
read-only cold discovery. The earlier RAM-lifetime limitation remains true of
the old candidate. See [current behavior](book-screen-and-continue.md).
