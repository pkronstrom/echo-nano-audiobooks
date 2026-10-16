#ifndef GUARDED_CREATE_H
#define GUARDED_CREATE_H
#include "../../src/fw.h"
/* OFFLINE RESEARCH ONLY. Creates and closes an EMPTY fixed-name file.
 * event_bytes is allocation preflight only; no content is written and the
 * result must never be accepted as a usable book companion. The physical
 * parent must have been freshly resolved/revalidated by the caller; an opaque
 * descriptor is not proof the original Unicode directory still exists.
 * Scope: FAT32/exFAT, 512-byte sectors, at most256 sectors/cluster, a single-
 * cluster parent, preflight event_bytes<=131072, fixed uppercase
 * BOOK.RSM/BOOK.BMK/BOOK.TMP. Native directory growth is always refused.
 * A bounded4096-sector FAT/bitmap prefix is checked with watchdog service. That
 * check is neither a reservation nor permission to call native growing write.
 * Caller must ensure no concurrent filesystem operation crosses this call;
 * fw_lock masks stock FS IRQs but does not supply a custom writer guard.
 * On an I/O failure after insertion, an invalid empty file may remain. This
 * adapter never deletes, truncates, repairs or retries an existing file.
 * Return 0 means a persisted empty entry; negative means refusal/failure.
 */
int guarded_create_empty(const u8 parent[42], const char *name,
                         u32 expected_device, u32 expected_fs, u32 event_bytes);
/* Offline allocation proof only: reserve an unreferenced contiguous run using
 * native FAT/bitmap mutation primitives. No directory length/cluster is published.
 * A failed/interrupted reservation may leak formerly free clusters. Never use
 * this as a standalone production API. Returns first cluster/count only after
 * checked native mutation and cold allocation-sector verification.
 * Approved refinement: select the actual FIRST free run through checked reads,
 * then call305e7f2 with the FAT cache pinned, or305d442 after proving the root
 * allocation-bitmap layout. The unbounded unchecked native search is bypassed.
 */
int guarded_reserve_native(u32 expected_device, u32 expected_fs,
                           u32 requested_bytes, u32 first_and_count[2]);
struct guarded_writer {
    u32 device, fs, first, clusters, total, offset, index, directory_lba, crc;
    int handle;
    u32 spc, heap, fat_lba, verified;
    u8 parent[42], name[12];
};
/* Experimental cold-browser adapter; hardware acceptance remains pending.
 * Only begin on an absent fixed name. Allocation
 * and I/O failures can leave an empty file and unreachable reserved clusters;
 * no automatic cleanup/retry is permitted. Supply512-byte packets except the
 * final packet. No growing native write is called. finish returns success only
 * after close, cold native reopen/read and complete content CRC verification.
 */
int guarded_writer_begin(struct guarded_writer *, const u8 parent[42],
                          const char *name, u32 device, u32 fs, u32 total);
int guarded_writer_packet(struct guarded_writer *, const u8 *, u32 length);
int guarded_writer_finish(struct guarded_writer *);
/* Only a closed, verified BOOK.TMP can be published as BOOK.M3U. Destination
 * absence, source identity/content and the complete rewritten sector are
 * checked again under the lock. Never close a pre-rename cached handle.
 */
int guarded_writer_publish(struct guarded_writer *);
void guarded_writer_abort(struct guarded_writer *);
#endif
