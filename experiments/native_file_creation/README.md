# Native file-creation probes

Research only: executes pinned stock Cortex-M3 instructions in Unicorn.
It never opens a device, changes firmware, or writes real storage.
The sector-backed harness below writes only its in-memory bytearray.

From the repository root:

```sh
builds/tools/test-env/bin/python experiments/native_file_creation/probe_stock_create.py
```

The11 assertion cases expose file-handle exhaustion, FAT error handling,
exFAT's ignored create failure, and exFAT duplicate insertion. Directory
resolution and selected disk-boundary operations are mocked. This original wrapper probe does not exercise actual allocation or write/close
persistence. The sector-backed harness below covers those native paths; full
crash consistency and hardware behavior remain untested.
See [the investigation](../../docs/automatic-book-preparation-investigation.md).

## Sector-backed harness

`disk_harness.py` executes native create, allocation, growing write, close,
directory reads, indexed open and file read with **only sector I/O and IRQ
lock/unlock substituted**. Its disk is a bounded bytearray, never a device or
host filesystem. The manually seeded geometry is deliberately synthetic, not a
complete mountable or on-disk-conformant FAT32/exFAT volume. It verifies the pinned stock hash before executing code.

```sh
builds/tools/test-env/bin/python -m unittest discover -s tests -p test_native_file_creation_disk_arm.py
```

Unicorn JIT needs execution outside the macOS sandbox (otherwise host SIGILL).
The12 tests cover FAT32 and exFAT1024-byte creation, cold emulator reopen,
persisted FAT chains/exFAT allocation bits, FAT directory expansion, duplicate
FAT names, exhausted handles, sector-write failures, and a cut before every
native sector write in ordinary1024-byte creation. The interruption checks only
establish that these fixtures do not expose a complete1024-byte length before
close; they do not prove transactionality, allocation-leak freedom or hardware
crash consistency. Sector writes are atomic in this model; torn sectors, nested
Unicode directories, real mount parsing, concurrent changes, stale devices,
read-only drivers and physical latency remain outside this fixture.

The fixture manually seeds already-mounted geometry:512-byte sectors, one
sector/cluster,64 clusters, FAT LBA1, cluster heap LBA4. FAT32 root is cluster2.
exFAT uses bitmap cluster2 and root cluster3. Native packed globals are:

| Address | Value/purpose |
| --- | --- |
|03076b24 | FS type2(FAT32) or3(exFAT) |
|03076b25 | device kind3 |
|03076b26 u16 | cluster shift0 |
|03076b28 u16 | sector shift9 |
|03076b2c | device ID0x30002 |
|03076b30 | bytes/sector512 |
|03076b34 | sectors/cluster1 |
|03076b38 u16 | FAT32 reserved sectors1 |
|03076b3d | root cluster |
|03076b4b | cluster count64 |
|03076b4f | cluster heap/bitmap sector4 |
|03076b53 | partition offset0 |
|03076b5b | exFAT FAT LBA1 |

Current-directory create uses `"."` after seeding FAT current cluster03077664
or the42-byte exFAT descriptor03078a5c. The descriptor has cluster at0,
byte length at4 and flags1 at12. This avoids sending a Unicode path through
the stock byte-oriented short-path resolver. Directory descriptor ancestry is
not modeled. Native file/cache reset is0305bddc. Sector read0306b716 and
write0306b75e both take `(device,LBA,count,buffer)` and return0 for success.

Confirmed stock hazards are characterization tests, **not safe behavior**:

- exFAT's two inactive slot scanner writes a three-entry set and overwrites an
  active third entry. No absence check is provided by insertion.
- A full exFAT allocation bitmap makes the writer's allocator pass cluster0
  into bitmap mutation, issuing an invalid sector request in this fixture.
- Failed directory write-cache reads are ignored by both FAT and exFAT entry
  writers. A stale cache can overwrite unrelated neighboring entries while
  returning0. Cold file verification alone cannot undo that corruption.
- Failed data writes can report the requested byte count. Cold readback catches
  the missing data; warm cache or close return codes do not establish success.
- FAT directory expansion returns a created FCB index one past the actual entry;
  cold native name re-resolution is necessary before indexed reopen.
- exFAT root directory expansion with the seeded512-byte descriptor attempts an
  invalid sector request. Directory growth is not validated or safe to enable;
  the exact scope of this stock arithmetic/descriptor behavior needs more audit.

The harness deliberately stops any invalid sector request. It does not replace
the failing native allocator, insertion, cache or flush algorithms with mocks.
