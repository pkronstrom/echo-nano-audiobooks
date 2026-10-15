# Echo Nano boot-loop and recovery lessons — 14 October 2026

## Current state and decision

**Stock normal menu restored and confirmed by the user. P4a failed hardware
boot acceptance. Do not reflash the same image or publish it as usable.**
The root cause of P4a's boot loop is unresolved. No further device write is
needed now. Start the next investigation offline, preserve the failed image,
and isolate changes before proposing another hardware test.

Device: Echo Nano HW 1.0.0, originally SW 1.7.0. SD card was removed during
the initial test. The restored image contains stock 1.7.0 code with build date
20261014. The normal menu is confirmed; a fresh About/version reading and
audio test after recovery have not been recorded.

## What happened

1. P4a was hash-verified on internal storage, safely ejected, and installed.
   The user saw the firmware-update screen, then repeating logo animation with
   roughly 30-second pauses. It did not reach the menu.
2. Normal USB storage still worked initially. A later-dated stock image was
   copied and verified, but the next restart did not visibly start an update.
   Subsequent recovery reads showed **both complete application regions were
   still P4a**, not stock. Copying a restore file is not proof of restoration.
3. Several recovery-entry attempts produced no USB enumeration. We incorrectly
   described a 10-second Power hold as power-off; it is a forced restart.
   Recovery eventually appeared as `2207:262d` Loader with a black screen.
   The exact final button timing was not conclusively recorded. Do not turn
   the proposed Power + Previous sequence into a claimed proven recipe.
4. Both complete 11 MiB P4a regions were saved. A bounded USB recovery write
   restored the second region first, verified every byte by readback, then
   restored and fully verified the first region.
5. After unplug/restart, the user saw firmware updating again, then confirmed
   the normal menu. The previously staged stock file likely explains this
   additional update; its consumption was not inspected afterward.

## Operational lessons

- **Host tests, emulation and review are not boot acceptance.** P4a had 145
  passing suite checks, 14 final targeted checks, and resolved Fable findings,
  yet failed on hardware. Do not claim a safety guarantee from those results.
- **Two firmware regions are not a retained stock rollback.** Both were
  overwritten with P4a. Date selection and duplicate headers do not establish
  automatic recovery from a valid image that crashes after boot.
- **Do not repeatedly guess button combinations.** Record screen behavior,
  exact gesture, cable/port and USB enumeration. A logo appearing and going
  dark is not enough to identify recovery or a dead device.
- **Power hold means restart.** For entry from a genuine powered-off state,
  Previous/Up held before connecting USB worked earlier. A reset-assisted
  variation was suggested later, but its precise successful execution remains
  uncertain. A black recovery screen is compatible with successful USB access.
- **Identify the USB mode before commands:** normal `071b:3203`, recovery
  `2207:262d`. `rkdeveloptool ld` reported Loader. That label alone does not
  independently establish ROM versus installed-loader identity.
- **Accessory approval matters on macOS.** Earlier kernel evidence explicitly
  showed transport restrictions blocking registration. Normal and recovery
  identities can require separate approval. Do not change global security
  settings or assume every later failure is an approval problem.
- **Disk numbers are transient.** An external SSD was disk4 earlier; the Nano
  later became disk4. Match USB identity/path, volume and capacity each time.
- **Use 32-sector transfers on this tested path.** Two 16 KiB reads matched;
  a single 128-sector request timed out. Subsequent exchanges failed until a
  normal boot/re-entry. Four 32-sector reads and the large sequential read
  worked. Do not reuse upstream's default 128-sector transfer size untested.
- **Distinguish error domains.** `RKU_ReadLBA err=-8` here means the tool's
  `ERR_FAILED` from CSW status 1; a libusb `-8` elsewhere means overflow.
- **Do not assume no update screen means a failed stock boot.** First check
  the staged file and installed bytes. Here stock had not been installed in
  either application region before the direct recovery operation.
- **Generic FiiO recovery pages are not Nano instructions.** The two supplied
  pages describe Play/Pause entry and an on-screen wipe menu. Their applicability
  to this Nano was not established; no wipe was performed.

## Addressing and backup coverage

The loader reports 983040 sectors (480 MiB). The successful logical read contains
974848 sectors (476 MiB), SHA256
`34bc70c37f4b250a4a0fa4672aa5910c1d32df1ec62262bdfaebc93d0913d79f`.
The FAT volume begins at byte237010944, declares 511936 sectors of512 bytes,
and ends exactly at the read boundary. Four independent samples matched later.

The analyzed factory loader's device-type-3 read/write wrappers add8192 sectors
(4 MiB). Six actual-byte emulation checks confirmed that mapping with backend
I/O intercepted. This explains the reported-size/readable-extent difference;
it does not make the logical dump a backup of the reserved prefix, loader, NAND
spare/OOB or every physical flash byte. Installed loader identity remains
unproven. Do not write logical images to physical address zero.

## Exact successful restore scope — evidence, not a generic recipe

| Item | Value |
| --- | --- |
| Second application region restored first | Logical LBA26624, 22528 sectors |
| First application region restored second | Logical LBA0, 22528 sectors |
| Bytes in each write/readback | 11534336 (11 MiB) |
| Stock restore package | `builds/phase4a/recovery/NANOV170.IMG` |
| Package SHA256 | `b251de1eb74e9e3eea9a206cf9a0a034a8371f57265e959c733bb8ae2e62d57d` |
| Payload SHA256 | `8e931d60a034055fd0350004edbf00eb9151689d00ca0e58e625aaac1ffff51f` |
| Failed P4a package SHA256 | `01c28d12759aea3f93125e4168c9044e8a324f3eead875bb52ae04834aa4b494` |

The restore payload excludes the downloadable image's final four-byte package
CRC. Source package CRC and SHA256 were verified; comparison with original stock
showed changes only to the two date fields and package CRC. Both written regions
were read back in full and matched exactly before the user restarted.

The isolated writer allows only `wl`, the two start LBAs above, and exactly
11 MiB input. Its communication layer bounds every request to those application
extents, at most32 sectors, subcode0, and rejects any nonzero CSW status. The
runner pins payload/pre-write hashes, checks one matching Loader device, and
requires verified second-region completion before writing the first.
No erase, reset, loader-download or filesystem-write command was sent during
the direct recovery. It is local diagnostic tooling, not a validated portable
release utility. Never apply these offsets to another device/layout blindly.

## Evidence and next-agent checklist

Local evidence is intentionally ignored by Git:

- `builds/device-check/nano-lba-backup-a.partial` and adjacent JSON metadata.
- `builds/device-check/backup-layout.json`.
- `builds/device-check/verify-20261014-121559/`: independent pre-flash samples.
- `builds/device-check/post-bootloop-20261014-125232/`: P4a headers after failure.
- `builds/device-check/restore-preflight/`: complete before/after regions,
  stock payload, guarded runner, write/readback logs and result JSON files.
- `builds/tools/rkdeveloptool-read32/` and `rkdeveloptool-restore32/`.
- `builds/rea-factory/test_lba_mapping.py` and `lba-mapping-tests.log`.

Before another test: diagnose the failed build offline; do not simply change
its date. Prepare a minimal test with an explicit boot checkpoint, recheck the
actual device/layout and recovery artifacts, and account for the installed
20261014 stock date when preparing a later build/restore pair. Inspect the
internal root for leftover update files. Keep original release manifests as
historical evidence and consult this incident status before using them.

Related: [detailed incident record](device-test-and-restore.md),
[factory loader analysis](factory-loader-analysis.md), [RAM audit](ram-safety-audit.md).
FiiO pages reviewed: [566888](https://www.fiio.com/newsinfo/566888.html) and
[518429](https://www.fiio.com/newsinfo/518429.html).

## Follow-up: shared loader bug (offline correction, hardware test pending)

After the menu-hook-bypass diagnostic booted, Shuffle froze. Stock dated20261016
was restored and the user confirmed normal boot. A new real-stock-reader
regression then reproduced payload corruption: the stock byte reader's aligned
bulk + partial-tail path reads the tail from the wrong sector. P4a's10568-byte
request corrupted its final328 bytes, including memcpy/memset and constants,
while reporting success. The previous tests mocked away this failure boundary.

The correction rounds the request to10752 bytes and checks padding/BSS bounds;
147 tests pass, including real byte-reader and payload-init execution for both
firmware-region mappings. The new 20261017 candidate is unflashed. See the
[investigation](p4a-bootloop-investigation.md) for hashes and evidence.

Lesson: for injected code loaded from flash, test exact byte-for-byte loading
through the real firmware read implementation, including its non-sector-sized
boundary cases. Mock hardware sector I/O, not the byte reader whose behavior
is under test. A correct magic word and success return do not prove the rest
of the payload loaded correctly.
