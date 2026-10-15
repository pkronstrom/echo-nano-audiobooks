# Nano community patch review

Originally checked 12 October 2026; rechecked 15 October 2026 against public GitHub API data and the working source.
Recommendation for the first device test: keep the existing refresh/library
improvements, and retain stock clocks, idle behavior and wheel polling. No newer
upstream fix was found to integrate.

## Exact upstream state

The current upstream `main` remains our pinned
[`ea4e6dc2cb386483093c7b045b6e85f26939ce2e`](https://github.com/maaraneasi/nanitecfw/commit/ea4e6dc2cb386483093c7b045b6e85f26939ce2e),
committed 8 October 2026 at 12:16:48 UTC. That commit changes the default image date.
The public issues and pull-request API queries, including closed items, both
returned empty lists. The only listed fork,
[`zezic/nanitecfw`](https://github.com/zezic/nanitecfw), is at
`ba9a39c20f3fc4030f8c04de51000c61659dbe7e` (6 October 2026, 15:43:59 UTC):
zero commits ahead and two behind our pin. It has no additional changes to import.

Recheck links: [commits](https://api.github.com/repos/maaraneasi/nanitecfw/commits?per_page=20),
[all issues](https://api.github.com/repos/maaraneasi/nanitecfw/issues?state=all&per_page=100),
[all PRs](https://api.github.com/repos/maaraneasi/nanitecfw/pulls?state=all&per_page=100),
[forks](https://api.github.com/repos/maaraneasi/nanitecfw/forks?per_page=100),
[fork comparison](https://api.github.com/repos/maaraneasi/nanitecfw/compare/ea4e6dc2cb386483093c7b045b6e85f26939ce2e...zezic:main).
Raw responses are preserved locally under `builds/research/upstream-20261012/`.
This is a snapshot, not a claim that future patches cannot appear.

## Improvements already included

| Change | Local implementation | Available device evidence |
| --- | --- | --- |
| Faster library refresh | `src/cfw.c`: 4 KB small-read cache, compact sort keys and hashes | Upstream reports 148 to 28 seconds for 2,000 FLAC-heavy tracks |
| Whole-library shuffle and shortcut | `patches/shuffle*` | Upstream marks playback and scope tested; original new icon was not confirmed |
| Recent Albums and separate Artists / Album Artists | `patches/recent_albums*`, `library_menu*`, `track_artists*` | Upstream marks tested |
| Bounded unsupported-track skipping | `patches/skip_unsupported.patch` | Upstream marks tested; this does not resolve every unsupported-file freeze |
| Refresh timing log | `src/prof.c`, `src/cfw.c` | Upstream marks tested |

The evidence above belongs to upstream's build and collection, not our device.
See its [pinned README](https://github.com/maaraneasi/nanitecfw/blob/ea4e6dc2cb386483093c7b045b6e85f26939ce2e/README.md).
Our exclusion work adds scanner hooks and reduces the sort-key cache from two
windows to one to fit memory. The upstream speedup therefore must not be promised
for this build; measure its own `CFWLOG.TXT` on the actual card.

## Experimental power changes

The [6.0.5 power commit](https://github.com/maaraneasi/nanitecfw/commit/f5f2de5df1091993aaeb55ac73ed1f378f6659fb),
7 October 2026 at 09:19:04 UTC, is already present in source. The local Makefile
excludes both power patch files unless `POWER_SAVE=1` is explicitly selected.

Inspection of the unchanged local patches shows:

- `power_clocks.patch` lowers codec clock requests. Its comments describe
  simulated decode-core targets of 144 MHz for MP3/WMA/AAC/WAV, 240 MHz for some
  OGG modes, and 288 MHz for FLAC/ALAC. These are not measured battery gains.
- `power_idle.patch` changes resident main-loop sleep gating at `0x0306a16c`
  and `0x0306a174`, permitting WFI while the screen is on except during an
  inhibit condition.
- The same idle patch changes four wheel-timer setup sites from 400 to 1,000
  microseconds, including music-service initialization. Thus its switch bundles
  sleep and wheel changes; it is not an isolated idle-only experiment.

Upstream explicitly leaves battery improvement unmeasured, warns that hi-res
24/192 FLAC has not been tested, and notes possible lost steps during very fast
wheel movement. These are reasons for a separate later A/B test, not reasons to
mix power experiments into first audiobook/resume validation.
[Source patches](https://github.com/maaraneasi/nanitecfw/tree/f5f2de5df1091993aaeb55ac73ed1f378f6659fb/patches).

## Other community evidence and limits

In the [author's Nano discussion](https://www.reddit.com/r/snowsky/comments/1wz1el2/snowsky_nano_the_proper_shuffle/),
another owner reports faster scanning with about 8,000 songs; one reports roughly
ten minutes of smooth playback. The author says battery changes remain
unmeasured. These firsthand anecdotes support trying the existing baseline, but
do not establish long-session stability or a battery improvement. Gapless and
offline scrobbling appear as ideas, not downloadable Nano fixes in this revision.

RECHO's [author announcement](https://www.reddit.com/r/DigitalAudioPlayer/comments/1wyz298/recho_092_sd_card_mp3_bug_fixes_snowsky_echo_mini/)
explicitly limits tested support to Echo Mini 8 GB, despite an inconsistent Nano
mention elsewhere in the post. Its gapless/fast-navigation claims are not
Nano-compatible patch evidence. Do not transplant its firmware or addresses.

The [official Nano changelog](https://forum.fiio.com/note/showNoteContent.do?id=202605161533005115232)
lists V1.7.0 as its latest entry in this check. Our exact V1.7.0 base already
contains the earlier official library-speed, OGG previous-track and power-on
sequence fixes; these are not additional community patches to apply again.

For tomorrow: test books, FLAC meditation files, music shuffle and restart/resume
with stock power settings; retain the scan log. Once those pass, a separately
dated power experiment can compare the same files, EQ, volume and screen state,
including long sessions, seeking, rapid wheel input and high-rate FLAC. No
power experiment or new upstream firmware was built or flashed by this review.

## Recheck — 15 October 2026

Main is still ea4e6dc2cb386483093c7b045b6e85f26939ce2e; no newer commits or
pull requests. A new fork, tuanbuinov09/nanitecfw, is identical (0 ahead/behind).
zezic/nanitecfw remains 0 ahead, 2 behind. No new code to integrate from these
repositories, and no new playback-speed implementation found there.

New [battery report](https://github.com/maaraneasi/nanitecfw/issues/1): one user
reports approximately 7 hours stock versus still playing at 10 hours with custom
firmware, using 32 kHz MP3 at volume 50. There were no comments at this check.
This is useful anecdotal evidence, not a controlled result for our build; our
power patches remain disabled. Revisit separately after speed CPU requirements
are understood. Do not lower decoder clocks while assessing time stretching.

ECHO-Firmware-Tool latest commit remains 32e272515e579ee98ee44e051fc3017a7f9b5927
(9 October), documenting skip-Switch behavior in MASKROM. It offers no new
audiobook playback feature in these latest changes.

Raw API evidence, issue comments and fork comparisons: builds/research/upstream-20261015/.

User priority update: audiobook speed (1, 1.25, 1.5, 1.75, 2x, preferably
pitch-preserving) precedes remaining durable-resume enhancements. Next work is
exact-stock PCM/codec tracing and CPU/RAM feasibility, following the existing
audiobook usability plan. Automatic creation of missing BMK files is a separate
backlog item: current journal code requires an existing 1024-byte companion.
