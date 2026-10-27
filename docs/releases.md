# Echo Nano audiobook firmware: patch release

> [!CAUTION]
> **Use at your own risk. I take no responsibility for what happens to your
> device.** This is unofficial, experimental firmware. Flashing or using it can
> brick your Echo Nano, lose the data on it, void its warranty, etc. A firmware
> that does not boot may not be recoverable. If you go ahead, you accept all of
> the risk. The software is provided "as is", without warranty of any kind; see
> `LICENSE`.

This patch turns your own copy of FiiO's official Echo Nano **V1.7.0** firmware
into two images: the custom firmware with the audiobook features, and a recovery
image with FiiO's unmodified code. The ZIP contains only the changed bytes, not
FiiO's firmware. You need Python 3.10 or newer, and no compiler, packages or
Internet connection.

**Tested on:** Echo Nano hardware 1.0.0 with the official firmware V1.7.0 only.
Features, known issues and the source code:
<https://github.com/pkronstrom/echo-nano-audiobooks>

## For users

1. Check the ZIP against the SHA-256 published with the release.
2. Download the official V1.7.0 `NANOV170.IMG` from
   [FiiO's firmware page](https://forum.fiio.com/note/showNoteContent.do?id=202605161533005115232).
   The patch accepts only this file, SHA-256
   `54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116`.
3. Open a terminal in the extracted folder and run:

   ```sh
   python3 apply_release.py --input /path/to/NANOV170.IMG --output ./nano-ready
   ```

   On Windows, use `py -3` if `python3` does not work. The script never changes
   the input file and refuses an output folder that already exists.
4. Copy `nano-ready/custom/NANOV170.IMG` to the root of the player's
   **internal** storage, not the SD card. Eject it safely and restart the
   player. It shows an update screen while it installs, then the menu.
   **About** shows P4e.
5. Set up your card as described in `audiobooks.md`, then run
   **Media Library → Media Library Refresh** once.

The script writes:

- `nano-ready/custom/NANOV170.IMG`: the custom firmware.
- `nano-ready/recovery/NANOV170.IMG`: FiiO's unmodified code, dated one day
  later. Keep it on your computer.
- `nano-ready/checksums.json`: the dates, the source commit and the image hashes.

### Dates

The player installs the image with the **newest** build date. The default date
is `default_date` in `patch.json`, which is newer than stock V1.7.0. If your
player already has a custom build with the same or a newer date, choose a later
date:

```sh
python3 apply_release.py --input /path/to/NANOV170.IMG --output ./nano-ready-2 --date 20261201
```

The recovery image is always dated one day after the custom image. Don't pick a
date far in the future: an official FiiO update dated earlier than your custom
image would be ignored.

### Recovery

**If the player still boots**, copy `nano-ready/recovery/NANOV170.IMG` to its
internal storage the same way and restart. That puts FiiO's code back. If you
have installed a custom image dated later than that recovery image, run the
script again with a later `--date` and use the new recovery image.

**If it does not boot**, copying a file will probably not help. Read the
Recovery section on the project page before you try anything. Holding Power for
about 10 seconds forces a restart; it does not switch the player off.

### Files

- `apply_release.py`, `rknano_fw.py`: create the images from `patch.json`. The
  script checks the stock hash, the result hash, the CRC and the header copies
  before it writes anything.
- `prepare_book.py`: prepares audiobook folders on a computer; see
  `audiobooks.md`.
- `SHA256SUMS`: hashes of the other files in the ZIP.
- `approved-icons.json` and `licenses/`: sources and licenses of the menu icons.
- `LICENSE`.

## For maintainers

The release builder copies this file into the ZIP as `README.md`, up to this
heading.

Build from a clean checkout, then build the ZIP:

```sh
make clean
make test AUDIOBOOK_DATE=YYYYMMDD
python3 tools/build_release.py --output builds/release/echo-nano-audiobooks-vX.Y.Z.zip
```

`--icons docs/icon-review.html` adds the optional icon review page for feedback
builds. The builder records the current Git commit and whether the source tree is
dirty. Dirty trees are rejected unless `--allow-dirty` explicitly marks a local
candidate. It verifies exact stock identity, CRC/header copies, unchanged
module/section layout, and unchanged graphics, fonts and other protected
resource sections. Language changes are allowed. The applier verifies ranges,
base SHA-256, reconstructed target SHA-256, CRC, header copies and layout
**before** optional restamping.

ZIP ordering, timestamps and permissions are fixed; identical files, source
metadata and compression environment produce identical archives. Publish the ZIP
plus its SHA-256 only; never upload complete custom/recovery firmware or the
original stock image. The builder prints machine-readable JSON, including
`archive`, `sha256`, `target_sha256`, `source_commit`, `source_dirty` and range
count. CI can run
`python3 -m unittest discover -s tests -p test_release_bundle.py` without stock;
real-stock integration cases explicitly skip when firmware is unavailable.

Patch schema 1 contains ordered, nonoverlapping changed byte ranges encoded as
hex, exact supported base/target SHA-256 values, image size, default date and
source metadata. Ranges reconstruct only the validated target from the exact
stock file; a checksum cannot be bypassed with a command-line override.

The recorded Git commit is provenance metadata, not proof that an arbitrary
existing `out/audiobook/NANOV170.IMG` was built from that commit. The builder
validates the image and patch but cannot reconstruct its build history. Do not
treat successful tests or CI as device acceptance.

### GitHub draft workflow

`.github/workflows/draft-release.yml` provides a manually dispatched draft build.
Supply an HTTPS URL to the raw official V1.7.0 IMG, a build date, and a new
candidate tag such as `v0.1.0-rc1`. The workflow verifies the known stock hash,
builds and runs the complete suite, compares clean rebuilds, and builds the
patch ZIP. Only that ZIP and its checksum are attached to a **draft prerelease**.
It does not publish the release. This GitHub workflow has not yet been executed;
its first hosted run remains a release acceptance step.

The draft workflow creates a new tag at the exact checked-out source commit
before creating the draft with `--verify-tag`. An existing tag is rejected, so a
new build cannot silently be attached to an older source tag. If creation stops
after the tag was made, inspect that partial draft/tag and choose a new candidate
tag or clean it up deliberately before rerunning.
