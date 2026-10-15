# Factory loader and recovery audit

2026-10-13. Offline REA 6.4.0 / Ghidra 12.1.4 and ARM Unicorn investigation.
The initial investigation was offline. Subsequent read-only checks are recorded
below. On 2026-10-14, application-only USB recovery writes and complete readbacks
succeeded after a P4a boot loop; the user confirmed the stock normal menu. See
[recovery lessons](recovery-lessons-2026-10-14.md) for the current outcome and limits.
Earlier no-write/pending statements below describe their historical checkpoints.

## Finding

The factory Nano loader has an application-independent upgrade check: USB VBUS
present and a low ADC channel-1 value during startup. This is stronger evidence
than the application USB-switch path alone. Stock 1.7.0 key-scan and browser code identify **Previous/Up** as the
evidence-based button candidate. Subsequent hardware checks confirmed entry with
Previous/Up held while connecting USB, and return to the normal menu. The exact
installed loader identity remains unverified.

Factory package: `NANO_F512M_HW_V1.0_SW_V1.4.0_HIFIDAC43131_3KEY_20260623_1024.img`
from [ECHO-Firmware-Tool](https://github.com/BlackVllad/ECHO-Firmware-Tool).
SHA-256 `a121dff253444d216dcedc5edcf25241be2ffdf97dbfbb1d1ae92e7a84b5ef11`.
This is the supplied 1.4.0 factory package, not a backup of the connected 1.7.0
unit. The repository's support provenance is a third-party attribution.

## Container and extracted stages

Used [Rockbox's RKFW/BOOT definitions](https://github.com/Rockbox/rockbox/blob/master/utils/rknanoutils/rkboottool/rkboottool.c)
to implement a bounded local extractor (`builds/rea-factory/extract.py`).

- RKFW header is 102 bytes; chip field `0x31` (do not apply the old parser's
  `0x30` label blindly).
- BOOT container: file offset 102, size 33,941. Its Rockchip CRC32 verifies.
- Update area: offset 34,043, size 23,068,672; two identical 11 MiB regions,
  each with matching leading/trailing RKnanoFW headers. This packaging is not
  evidence of a known-good rollback slot after an application update.
- Whole-package trailing ASCII MD5 verifies:
  `6fc84660616a6be4b439a2f8f629eabe`. Checksums establish internal integrity,
  not publisher authenticity or compatibility with an unobserved device loader.
- BOOT entries decoded using the documented per-512-byte scrambling transform;
  inverse transform verifies exact original bytes. Group1 unnamed: 13,184 bytes;
  NandBoot1: 2,048; NandBoot2: 18,432. Digests in `extraction.json`.

The stage-2 reset stub at `0x0300008c` copies 0x4494 bytes from `0x03000114`
to `0x0304a000`, switches the vector table, loads SP `0x03090000`, and branches
to vector entry `0x0304a8cf`. The analysis ELF maps the copied body to its actual
runtime address. Both original and relocated ELF section bytes are checked
against extracted bytes. The loader main reports version `4.15`, Dec 3 2025;
this is a loader string, not the application version.

## Upgrade decision before application launch

`loader_main` at `0x0304a8ce` checks the retained boot-request register:

- `0x18af`: skip application boot, replace request with `0x18ef`, enter the
  loader's USB path. This matches stock 1.7.0's software request.
- `0x18ef`: skip application boot and clear the retained request.
- `0x18bf`: a separate cleanup path calls the function pointer stored at ROM
  address `0x8c`.
- Otherwise, call the hardware condition check; a successful check also skips
  application boot and writes `0xffff18ef` to `0x5002004c`.

At `0x0304a820`, the condition check selects ADC channel1 (control low bits1),
starts conversion and waits up to 100 delay polls per sample. ADC values <=64
reset a high-reading counter; three consecutive values >64 reject entry.
It samples for up to 500 iterations while VBUS register `0x500100e8` bit1 is
set. With VBUS still present and no rejecting high run it returns true.
The SDK ADC register definitions corroborate channel/control-bit meanings;
the machine code is the evidence for this particular loader's thresholds.

Seven bounded Unicorn checks execute these exact bytes, mocking only ADC/VBUS
register reads and delay/logging callees: ADC0,64 accepted; ADC65,1023 rejected;
no VBUS rejected; intermittent high readings reset by low accepted; ADC timeout
rejected. See `test_upgrade_check.py` and `upgrade-check-unicorn.log`.
These checks do not calibrate milliseconds or emulate physical buttons/USB.

The selected upgrade branch reaches `0x0304d850`, which initializes the USB
controller at `0x60080804`, installs/enables the relevant interrupt and reconnects
it. The surrounding loader contains USBC/USBS transport signatures. The complete
host command protocol, successful enumeration and restore cycle are untested.

## Physical control correlation

Stock module0 samples ADC1 at `0x03065d96`; values <70 map to key8 at
`0x03065db4..0x03065dc8`. Stock browser module31 maps key8 to the function at
`0x0307b11a`, which decrements the selected row at `0x0307b13e`.
The factory recovery range <=64 lies inside that same key8 range.
Both stock module blobs were checked byte-for-byte against NANOV170.IMG.

This independently identifies Previous/Up as the candidate control. It does not
establish a boot/plug-in timing sequence, actual ADC readings, or whether this
unit has the same factory loader. See `builds/rea-factory/key-mapping.md` for
sampling, debouncing and event-dispatch addresses. No physical test was made.

## Application validation is not a crash watchdog

The normal boot routine at `0x0304ab00` tries application loading at offset0 and,
when configured, another offset held in `0x030880c4` (sector units). It updates
retained boot-attempt values `0x18df` / `0x18cf` / `0x18ef` around attempts.

Loader routine `0x0304d34c` checks the RKnanoFW signature, reads the mirrored
header, compares all 512 header bytes, reads startup module code/data and clears
BSS before handing off. Its failure return can lead to trying the second copy;
the normal routine eventually spins if its attempted loads return. No general
proof of automatic recovery from a correctly packaged application that later
crashes follows from these checks. A separate hardware entry route matters.

## Scope and limits

- Factory loader is available, so immutable ROM is not the only possible place
  for application-independent recovery entry. The ROM body itself is not in the
  update image and has not been extracted from the device.
- We have not proved the installed loader equals this factory loader.
- Button identity and startup timing require a read-only entry/exit device test.
- No claim of a complete flash backup, safe downgrade, automatic rollback or
  unbrickable custom firmware.
- Ghidra may omit hardware-register stores in pseudocode; branch-sensitive claims
  above were checked against its instruction listing and objdump/literal values.

## Evidence

Full dossiers under `builds/rea-factory/`; C and assembly excerpts saved beside
each JSON. Extraction and wrapper scripts are local analysis artifacts and must
not be used as flash images. The factory binaries remain local build artifacts.

| Dossier | REA Evidence ID |
| --- | --- |
| `boot1-reset.json` | `ev_3f8cd5041c8d23422aa7274f183cc3736c0100d286b59bfb2c7901e748d716a9` |
| `boot2-reset.json` | `ev_f381835f5086d10e5318828d6bae4e000f39dfb3f5c10ab7a28d5ee4e5ec54b8` |
| `loader-main.json` | `ev_989cdc89e306ea736943e47ea36c4c00ffe4b29539b66bbfb5baddc1217fa517` |
| `upgrade-check.json` | `ev_ce4df44bf9c317664bfeb357a8deb884b875b9b205019b89522dbd9c337ac1a6` |
| `boot-app.json` | `ev_1b16856c319aaa909b92a7e20f6a62381c8e269222c84b65b348bde6a5b32505` |
| `load-image.json` | `ev_0fc0ae2392e64e8583ac2e2e68b8d4de54ee6219cda8bde86c1a75dd6598ae77` |
| `loader-usb.json` | `ev_cadad7fb49c79ba14ff3722a5dc72201a2347c826a2b0896440136880b8f39d6` |

## Device observation: 2026-10-13 15:14 EEST

User reported connected after the proposed power-off, hold Previous/Up, connect
USB sequence. macOS system_profiler observed `2207:262d`, bcdDevice1.00,
`composite_device`, location0x02100000, replacing normal `071b:3203`.
IORegistry independently reported vendor8711/product9773 (same hex IDs).
The Nano user-storage disk was absent; the unrelated Samsung disk remained.
This supports physical entry into a Rockchip recovery/download state without
using the application USB command. The exact MaskROM versus loader stage is
not established by VID/PID alone.

The current rkdeveloptool `ld` still reported no devices. IORegistry showed
`!registered`, `!matched`, UsbEnumerationState2; system_profiler also logged
interface/plugin errors. Thus descriptor visibility is not proof that host
command transport or flashing works. No reset/write/read-flash command was sent.
Evidence: `builds/device-check/button-entry-usb.json` and
`builds/device-check/button-entry-ioreg.txt`. Normal-boot return remains to test.

### Return to normal confirmed

After the user reported completing the disconnect/power/reconnect sequence,
IORegistry again showed ECHO NANO `071b:3203`, registered/matched with active
configuration1. `diskutil list external physical` showed the normal 262.1MB
DOS_FAT_32 ECHO NANO volume on disk5s1. Evidence:
`builds/device-check/return-normal-ioreg.txt` and the read-only disk listing.
Thus physical entry to the observed Rockchip USB state and return to normal
storage have both been observed on this unit. Recovery command transport,
flash readback and restoration remain unverified; no firmware was written.

### Mac enumeration blocker identified

Second recovery-entry attempt: macOS kernel at 2026-10-13 15:18:09 reported
`device functionality blocked by transport restrictions` for port0x02100000,
followed by `device will not be registered for matching`. libusb inventory
excluded the Nano entirely, before rkdeveloptool's VID/PID filtering. Its source
accepts vendor2207 and bcdUSB0201, so adding this ID is not the identified fix.
Evidence: `recovery-retry-kernel.log`, `recovery-retry-libusb.log`, and
`recovery-retry-ioreg.txt` under builds/device-check.

Next action is user approval of this new USB accessory on the unlocked Mac.
Normal Nano and recovery identify differently and may need separate approval.
No global accessory-security setting was changed and no firmware command sent.

### Read access confirmed after accessory approval

Once approved, rkdeveloptool listed a single `2207:262d` device as Loader;
IORegistry showed registered/matched. Read-chip-info returned
`43 32 36 32 00 00 00 00 55 53 42 43 00 00 00 00`.
Read-flash-info reported 983040 sectors (480 MiB), 512 KiB erase block,
8 KiB page. The utility's `SAMSUNG, value=00` manufacturer label is its
interpretation of returned metadata, not independent chip identification.

Two independent 32-sector reads at LBA0 returned identical 16384 bytes, exactly
matching the first 16384 bytes of official NANOV170.IMG. SHA256:
`cca34e66258ce621d35512dfdec1e240a2d88c17d8117b80b332d4d038d4df73`.
Thus macOS can read actual application flash through this loader. A 128-sector
single request timed out after20seconds and its child process was stopped.
No write/erase/reset/download-boot command was sent.

Prepared an isolated diagnostic rkdeveloptool build in
`builds/tools/rkdeveloptool-read32`: DEFAULT_RW_LBA32, CMD_TIMEOUT5000ms,
and an entrypoint allowlist of ld/rci/rfi/rl only. An attempted `wl` invocation
was rejected before USB setup. After a confirmed normal boot and fresh recovery entry, chip-info, flash-info
and a 32-sector read succeeded. The diagnostic tool then read 128 sectors as
four 32-sector requests: all 65536 bytes matched the official stock image prefix.
A full logical-LBA backup remains pending; its coverage must not be confused
with physical NAND, IDB/bootloader, spare/OOB bytes or calibration storage.


### Large read result after verified normal boot

The user confirmed the normal menu worked, then re-entered recovery. Repeating
chip-info, flash-info and LBA0/32 succeeded. Four 32-sector transfers also
matched the stock image's first 64 KiB. A sequential read of the reported
983040-sector extent then saved 499122176 bytes (476 MiB), stopping at LBA974848.
The log reports RKU_ReadLBA error -8, which this tool defines as ERR_FAILED:
a matching CSW returned status 1. This is distinct from libusb overflow -8.
Why the final 8192 sectors are unavailable is not yet established.

Retained file: `builds/device-check/nano-lba-backup-a.partial`, SHA-256
`34bc70c37f4b250a4a0fa4672aa5910c1d32df1ec62262bdfaebc93d0913d79f`.
The adjacent `.partial.json` records size, digest and incomplete status.
All first 0xb00000 bytes (11 MiB) match the official stock 1.7.0 image exactly.
The official file has four additional trailer bytes; the complete downloadable
file does not match the same-length flash prefix. Do not equate package trailer
bytes with flashed application payload.

This is a retained partial logical backup, not a verified full-chip backup or a
proven restore procedure. No write, erase, reset or download-boot command was
sent. Further USB reads were stopped so the user could disconnect and leave.


### Offline layout inspection of the retained read

`builds/device-check/backup-layout.json` records a sector-aligned header scan.
Two complete 11 MiB regions at logical offsets 0 and 0x00d00000 match the stock
1.7.0 payload byte for byte, including the matching header at declared image
length 0x00a58000. A stale-looking header at 0x00b00000 lacks a matching tail;
a header signature alone must not be counted as a valid firmware copy.
A third matching image occurs inside the filesystem and is not evidence of a
third boot slot.

FAT32 primary boot sector is at 0x0e208000 (237010944 bytes), with its backup
six sectors later. Both report 512-byte sectors, one sector per cluster and
511936 total sectors. Thus the filesystem ends at exactly:

    237010944 + 511936 * 512 = 499122176 bytes

This is precisely the retained read length and the first rejected LBA boundary.
The complete declared FAT volume lies inside the read; this does not establish
filesystem consistency or verify every byte with a second independent read.

Factory-loader assembly at 0x0304ce00 and 0x0304ce1c contains storage wrappers
adding 8192 sectors (4 MiB) before calling lower read/write routines. This is
consistent with a reserved prefix excluded from a logical-LBA view and the
480-versus-476 MiB difference. The installed loader is not yet identified and
the USB dispatch-to-wrapper chain remains to be verified, so this is a supported
mapping hypothesis, not proof that the missing range has been backed up.

Next device session should start with independent small reads of both firmware
regions and the final valid sectors, compared with this saved data. Before any
recovery write, establish the precise command/address mapping and preserve the
loader. A bulk restore of this partial file is not an approved procedure.

### 2026-10-14: dispatch mapping corroborated offline

Factory USB worker 0x0304a10e dispatches opcode 0x14 at 0x0304a16e
through 0x0304cabc; opcode 0x15 at 0x0304a192 uses 0x0304cae2.
These select initialized device entries by type via 0x0304ca20 and tail-call
entry offsets +12 / +16. The device-type-3 entry at 0x0304e460 contains
Thumb pointers 0x0304ce01 and 0x0304ce1d. Both wrappers add 8192 sectors
before backend storage calls (read 0x0304ae3c, write 0x0304ae7e).

`builds/rea-factory/test_lba_mapping.py` executes the actual dispatch, lookup,
and wrapper instructions for type 3 with only the backend I/O intercepted.
Six cases passed: read/write at logical LBA0, 26624 and 974816; all preserve
count32 and buffer address, translating LBA by +8192. Log:
`builds/rea-factory/lba-mapping-tests.log`. The initial sandbox run could not
start Unicorn JIT; the permitted offline rerun passed. No device write occurred.

For this backend, 983040 physical sectors minus the 8192-sector prefix equals
974848 logical sectors, matching both the retained backup and filesystem end.
This resolves the factory-code mapping hypothesis for device type3; it does not
identify the installed loader or establish the prefix's exact contents. Do not
restore this logical image at physical address zero or send a factory package
as a raw application image.

Next verification reads: 32 sectors at LBA0, 26624 (second stock region),
462912 (FAT boot sector), and 974816 (last valid block), compared against the
retained backup. Stop on any command error or mismatch. No write is needed for
these checks.

### 2026-10-14: independent device spot checks passed

After reconnection, the Nano enumerated as 2207:262d Loader. Chip and flash info
matched the earlier responses. Four separate 32-sector reads at logical LBAs
0, 26624, 462912 and 974816 each returned 16384 bytes and matched the retained
backup exactly. This independently verifies samples from both firmware regions,
the FAT boot sector and the end of the accessible volume; it is not a second
full-backup comparison or a restore test. Evidence and SHA-256 values:
`builds/device-check/verify-20261014-121559/results.json`.
No write, erase, reset or download-boot command was sent. All reads completed.
