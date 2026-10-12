# Echo Nano firmware requirements and phased delivery

Prepared for the implementation agent, 12 October 2026.

Extend the FiiO Snowsky Echo Nano into a convenient offline player for music, audiobooks and meditation recordings. Reuse the existing Nano shuffle and library patches where practical. Deliver useful, testable behavior in small phases, keeping the device's compact physical-control experience.

This is a product specification and research brief, not a prescribed implementation. Investigate the actual firmware and patch source before choosing an approach. Earlier conversational estimates of difficulty and available hooks are hypotheses, not verified engineering facts.

## Scope and priorities

| Requirement | Priority and status |
| --- | --- |
| Keep audiobook and meditation recordings out of general music playback and the music library | Required, early phase |
| Proper shuffle across eligible music, using the existing community shuffle patch | Required baseline to reuse and verify |
| Local M3U playlists referencing existing files with relative paths | Required, early phase |
| Predictable correct ordering of multipart audiobook chapters | Required |
| Independent resume position for each audiobook | Required |
| Audiobook seeking | Required; prefer 30-second backward and forward jumps, but use an easier workable mechanism if necessary |
| Dedicated Audiobooks menu | Desired if feasible |
| Dedicated Meditations menu | Desired if feasible; interaction design remains open |
| Meditation folders and individual file selection | Preserve the user's existing workflow |
| Review and improve existing and new activity icons | Required design round; larger, clearer and prettier icons, with the final design approved by the user |

Music improvements should become usable before the complete audiobook experience is finished. The user wants to approve every additional feature and have input on meaningful interaction choices. Do not turn optional ideas into requirements without asking.

## Existing work and research starting points

Start with [NaniteCFW](https://github.com/maaraneasi/nanitecfw). Its README, checked on 12 October 2026, describes patches for the exact official Nano v1.7.0 image, including whole-card shuffle, faster library scanning, extra library views, Thumb-2 patches and C code running during library refresh. It identifies `src/hooks.txt`, `patches/`, `src/` and firmware packing tools as useful entry points. These are upstream claims; verify the selected revision and its behavior locally and on the user's device.

The README lists shuffle order not surviving power cycles and possible freezes on unsupported files. Those limitations matter when choosing a baseline. Do not silently enable experimental performance or power changes merely because they are bundled upstream.

Official resources:

- [FiiO Nano firmware downloads and changelog](https://forum.fiio.com/note/showNoteContent.do?id=202605161533005115232)
- [FiiO Nano FAQ and quick start guide](https://www.fiio.com/newsinfo/1132454.html)
- [FiiO Japanese support on seeking and ordering](https://support.fiio.jp/hc/ja/articles/60876814334617-Snowsky-ECHO-NANO%E3%81%AE%E3%82%88%E3%81%8F%E3%81%82%E3%82%8B%E8%A8%AD%E5%AE%9A%E3%81%AB%E3%81%A4%E3%81%84%E3%81%A6)

The support guide says file-browser ordering follows copy timestamps, while album views use track numbers. Verify this on the actual firmware; copy order is not an acceptable basis for audiobook chapter order.

Echo Mini projects may offer research clues, but their images and hardware assumptions must not be treated as Nano-compatible. This task is for Echo Nano only. Bluetooth additions and a full Rockbox port are outside this scope.

## Music separation

Audiobooks and meditation recordings must be excluded recursively from the general music library and its automatic playback selections, especially global shuffle. Exclusion is a library and playback-scope rule, not deletion: recordings must remain accessible for deliberate listening.

The configuration mechanism remains open. Possibilities include configurable root paths or marker files such as `.nomusic`; neither was selected by the user. Recommend the simplest maintainable option and ask if it materially changes how the user organizes the card.

Apply separation consistently to music browsing, global shuffle and any automatic continuation that might otherwise drift into non-music recordings. Explicitly opening a book or meditation recording should continue to work.

Illustrative organization only; do not require a migration to these exact folder names:

```text
/Music/Artist/Album/...
/Audiobooks/Book title/...
/Meditation/Phase 1/...
/Meditation/Phase 2/...
/Playlists/Electronic.m3u
```

## Shuffle and playlists

Reuse and validate the existing whole-library shuffle patch as a prerequisite. The resulting pool must contain eligible music only, across artists, albums and folders. Establish what the existing algorithm actually does before promising repeat avoidance, distribution guarantees or persistent shuffle state. Persistence across restarts is an open enhancement, not an approved requirement.

M3U files must point to existing audio files without making copies. Resolve paths relative to the directory containing the playlist, so relocating the whole collection together preserves references. Preserve listed order during ordinary playlist playback.

For example, `/Playlists/Electronic.m3u` may contain:

```m3u
#EXTM3U
../Music/Massive Attack/Mezzanine/01 Angel.flac
../Music/Boards of Canada/Geogaddi/02 Music Is Math.flac
```

The first version needs path-based entries only. Ignore comment and extended-info lines such as `#EXTINF`; displaying playlist-supplied titles or durations is not required. Handle normal playlist text conventions, spaces and the user's filenames. Missing entries must not hang playback or invalidate the entire playlist; choose and document a simple understandable fallback.

Playlist discovery, menu location, file-count limits, UTF-8 behavior and path normalization are implementation questions to investigate. Whether an explicit playlist may intentionally reference an excluded recording is a product question to resolve, rather than silently applying or bypassing the music filter.

## Audiobooks

Remember each book's position independently, including both the current chapter file and position within it for multipart books. Listening to music, another book or meditation must not overwrite that progress. Resume should survive normal shutdown and restart.

Verify chapter order in both browsing and actual playback. The user has noticed that file browsing does not appear to sort lexically. Provide deterministic ordering independent of copy timestamps and filesystem enumeration. Decide whether natural numeric ordering, lexical ordering, track tags or an explicit sequence best matches the user's real collection. Resolve this with representative filenames before finalizing the rule. Test unpadded names such as `1`, `2`, `10` as well as padded names such as `001`, `002`, `010`.

Provide usable seeking. Thirty-second backward and forward jumps are the preferred interaction; retaining a simpler existing seek mechanism is acceptable if it enables earlier delivery. Exact button mappings remain open because the small device has limited controls. Propose the mapping before changing established controls. Define behavior near chapter boundaries; cross-file seeking is not automatically required.

A dedicated Audiobooks menu is desirable if feasible. It may be a thin entry into the relevant folders; a rich author/series/progress library is not required. A book may be one file or several files, so determine how book identity is assigned and how chapter continuation respects that identity.

M4B embedded chapters, pitch-preserving speed adjustment, manual bookmarks, finished-book tracking and a new sleep timer are not approved requirements. Record them only as future possibilities if useful. Determine the user's real formats before introducing format-specific work or conversion requirements.

## Meditation workflow

The user has several folders of FLAC recordings organized into phases or series. They pick a folder, then a specific file, for example Phase 1 file 3, and may choose file 4 on a later day. Preserve the hierarchy and direct file selection.

The firm requirement is exclusion from the music library and music shuffle. The user accepted leaving the rest flexible: no forced audiobook-style resume, queue, series advancement or automatic next-session selection.

A Meditations menu could be a shortcut to the folder browser. Remembering the last selected folder/file, starting a session from the beginning, or suggesting the next file are design options to discuss; they are not mandatory behavior. Do not flatten all recordings into one list if that loses the phase structure.

## Phased delivery

### Phase 0 Establish the firmware baseline

Inspect the exact device firmware and relevant upstream revision, reproduce a compatible build, identify affected scanner/playback/UI code, and document recovery. Preserve a known working baseline. This is a short prerequisite, not an open-ended reverse-engineering project.

Exit result: a reproducible baseline with existing shuffle behavior understood and verified. Record source revision, firmware compatibility and unresolved upstream defects. A successful build alone is not proof of device functionality.

### Phase 1 Deliver music separation and shuffle

Add recursive exclusion while retaining deliberate access to the recordings. Integrate the existing shuffle behavior with the eligible music pool.

Acceptance: with music, books and meditation on the same card, music views and global shuffle include music only. The excluded recordings remain manually playable. Refreshing the library and restarting do not restore them to the music pool.

### Phase 2 Deliver relative M3U playlists

Add discovery and playback of local path-based playlists. Keep the UI small and support existing files rather than duplicated playlist folders.

Acceptance: a playlist spanning several music folders plays in the listed order. Relative references still work after moving the containing collection together. Comment lines are ignored, and missing tracks are handled without a freeze. Repeat music-separation checks after queue integration.

### Phase 3 Deliver dependable audiobook listening

Establish correct multipart chapter order, independent per-book resume and usable seeking. Add an Audiobooks entry if feasible; a file-browser route may serve as an intermediate working delivery.

Acceptance: interrupt Book A midway through a chapter, play music and Book B, restart the device, and reopen Book A at its saved chapter and position. A book copied in scrambled order still plays chapters correctly. Seeking does not erase progress or unexpectedly enter unrelated content.

If the work is larger than expected, split this phase into separately usable chapter-order, resume and seek increments. Do not defer every improvement until all three are complete.

### Phase 4 Refine navigation with user input

Evaluate Audiobooks and Meditations shortcuts, folder navigation and meaningful button mappings using the user's actual collection. Ask about unresolved interactions before committing to new behavior. This phase must not block the earlier music and audiobook deliverables.

Acceptance: the user can select meditation phases and files naturally and reach books conveniently, with no regression in music separation, playlists or resume.

### Phase 5 Clarify and improve activity icons

Review the existing icons and proposed new activity entries with the user. Current icons can be difficult to identify or read. Aim for larger, clearer and more attractive icons for music, shuffle, playlists, audiobooks, meditation and other existing activities where appropriate. The precise activity list and navigation layout should follow what earlier phases actually support.

First inspect the Nano's actual screen, icon resources and layout constraints. Present an inventory of current icons and a small set of proposed directions at realistic device size. Ask the user about visual style, recognizability and the balance between icon size, labels and visible menu items. Show meaningful alternatives before settling on the design; a specific style or replacement set has not yet been approved.

Favor distinct silhouettes and readable contrast, consistent treatment across existing and new entries, and usable selected/unselected states. Avoid adding detail that disappears on the small display. Keep navigation understandable while improving appearance. Resource substitutions and larger icons may have different technical costs; investigate rather than assuming both are simple theme edits.

Acceptance: the user reviews and accepts the proposed icon direction and layout, then the implemented icons are checked at native screen size and on the device where available. Existing activities remain recognizable, new activities are distinguishable, and labels and selection indicators do not clip. Design approval may happen earlier if it helps menu work, but icon refinement must not block delivery of working music and audiobook features.

## Engineering guidelines and completion evidence

Keep source changes focused and explain the actual integration points found through inspection. Reuse existing codecs and playback machinery where feasible; a full firmware rewrite is not the default. Document uncertain memory, queue or filesystem constraints rather than guessing them.

Use small representative fixtures for exclusion, paths, ordering and resume. Cover nested folders, non-ASCII names, missing files, normal restarts and switching content types. Check the user's FLAC meditation playback and existing music controls after changes. Distinguish host-tested behavior from device-tested behavior and give the user short manual checks when hardware testing is unavailable.

Each phase should produce a usable build or clearly identified blocker, build/recovery instructions, a brief validation record and a concise status update: what works, what remains uncertain, and what the next phase delivers. Preserve earlier working builds. Do not report a phase as functional solely because it compiles.

The agent may investigate technical choices independently. Ask the user when deciding meaningful new features or interactions: exclusion configuration, audiobook identity/order conventions, button mappings, explicit playlists containing excluded files, meditation shortcuts, and icon style/layout. Do not add unrelated enhancements or repeatedly ask about requirements already agreed above.
