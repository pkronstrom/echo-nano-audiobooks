# Echo Nano patch release

This package produces custom firmware from your own official FiiO Echo Nano
V1.7.0 firmware. It contains changed bytes and Python scripts, not a complete
FiiO firmware image. The current P3a build is a device-test candidate; successful
host tests do not establish device compatibility. Public release publication
remains pending recorded device acceptance.

## For users

1. Download and extract the patch ZIP from the project's GitHub release.
2. Obtain the original official `NANOV170.IMG` for V1.7.0 from
   [FiiO firmware downloads](https://forum.fiio.com/note/showNoteContent.do?id=202605161533005115232). Only this
   SHA-256 is supported:
   `54a45d233a23c3ce142d1da9c093cc40c46eba417aa91fe915ee867726f4a116`.
3. Install Python 3.10 or later. Open a terminal in the extracted patch folder.
4. Generate both images into a new directory:

   ```sh
   python3 apply_release.py --input /path/to/original/NANOV170.IMG --output ./nano-ready
   ```

   On Windows, use `py -3` instead of `python3` if that is your Python command.
   No ARM compiler, Python packages or Internet connection are needed to apply
   the patch. Input firmware is never modified. Existing output is rejected;
   choose a new directory for a retry.

The default custom firmware date is recorded in `patch.json`. The bootloader
selects the newer valid firmware copy. If the default is not newer than the
firmware already installed, explicitly choose a later calendar date:

```sh
python3 apply_release.py --input /path/to/original/NANOV170.IMG --output ./nano-ready-new --date 20261014
```

Use a date newer than both your installed custom and any recovery firmware you
have installed. The script cannot detect the installed date. Avoid unnecessarily
far-future dates. The stock recovery is always stamped one day after the custom
image, with matching header copies and recalculated firmware CRC.

Outputs:

- `nano-ready/custom/NANOV170.IMG`: custom firmware for the normal FiiO update procedure.
- `nano-ready/recovery/NANOV170.IMG`: stock behavior, later date, for recovery.
- `nano-ready/checksums.json`: generated dates, source revision and exact image hashes.

Keep the recovery image on your computer. Copy only the desired `NANOV170.IMG`
to the device when following FiiO's firmware update instructions; the script does
not copy to, update or flash a device. Read `audiobooks.md` for the device checklist
and book preparation. In this extracted bundle run `python3 prepare_book.py`
instead of the repository's `python3 tools/prepare_book.py`. FFmpeg is optional
and needed only for explicitly requested conversion/remuxing.

`SHA256SUMS` covers the archive members except itself. The downloaded ZIP should
also be checked against the release's separately supplied SHA-256. Checksums
identify accidental damage; obtain the ZIP and checksums from a trusted release.
No unapproved icons are installed; optional `icon-review.html` is for feedback.

## For maintainers

Build and test the firmware using the repository's documented ARM toolchain,
then build a patch bundle:

```sh
python3 tools/build_release.py --stock NANOV170.IMG --target out/audiobook/NANOV170.IMG --output builds/release/echo-nano-p3a.zip --icons docs/icon-review.html
```

Omit `--icons` if the review HTML is unavailable. The builder records the current
Git commit and whether the source tree is dirty. Dirty trees are rejected unless
`--allow-dirty` explicitly marks a local candidate. Build public releases from a
clean, tagged revision after device acceptance. It verifies exact stock identity,
CRC/header copies, unchanged module/section layout, and unchanged graphics,
fonts and other protected resource sections. Language changes are allowed.
The applier verifies ranges, base SHA-256, reconstructed target SHA-256, CRC,
header copies and layout **before** optional restamping.

ZIP ordering, timestamps and permissions are fixed; identical files, source
metadata and compression environment produce identical archives. Bundle the
latest preparation script and docs. Publish the ZIP plus its SHA-256 only;
never upload complete custom/recovery firmware or the original stock image.
The builder prints machine-readable JSON, including `archive`, `sha256`,
`target_sha256`, `source_commit`, `source_dirty` and range count. CI can run
`python3 -m unittest discover -s tests -p test_release_bundle.py` without stock;
real-stock integration cases explicitly skip when firmware is unavailable.

Patch schema 1 contains ordered, nonoverlapping changed byte ranges encoded as
hex, exact supported base/target SHA-256 values, image size, default date and
source metadata. Ranges reconstruct only the validated target from the exact
stock file; a checksum cannot be bypassed with a command-line override.

## GitHub draft workflow

`.github/workflows/draft-release.yml` provides a manually dispatched draft build.
Supply an HTTPS URL to the raw official V1.7.0 IMG, a build date, and a new
candidate tag such as `v0.1.0-rc1`. The workflow verifies the known stock hash,
builds and runs the complete suite, compares clean rebuilds, and builds the
patch ZIP. Only that ZIP and its checksum are attached to a **draft prerelease**.
It does not publish the release. This GitHub workflow has not yet been executed;
its first hosted run remains a release acceptance step.

For a local formal release, start from a clean checkout of the intended tag,
run `make clean`, `make test`, and a reproducibility check before invoking the
builder. The recorded Git commit is provenance metadata, not proof that an
arbitrary existing `out/audiobook/NANOV170.IMG` was built from that commit. The
builder validates the image and patch but cannot reconstruct its build history.
After checking the draft assets and recording device acceptance, the maintainer
can publish the draft explicitly. Do not treat successful CI as device acceptance.

The draft workflow creates a new tag at the exact checked-out source commit
before creating the draft with `--verify-tag`. An existing tag is rejected, so a
new build cannot silently be attached to an older source tag. If creation stops
after the tag was made, inspect that partial draft/tag and choose a new candidate
tag or clean it up deliberately before rerunning.
