#ifndef ECHO_M3U_H
#define ECHO_M3U_H
#include "fw.h"
#define M3U_PATH_UNITS 256
#define M3U_LINE_BYTES 1024
#define M3U_MAX_ENTRIES 512
/* Read at most len bytes from an absolute byte offset. Negative = I/O error. */
typedef int (*m3u_read_fn)(void *, u32 offset, u8 *dst, u32 len);
/* Called in listed order with normalized absolute UTF-16 paths.
 * Return 1 when resolved, 0 when missing/unusable; negative aborts. */
typedef int (*m3u_entry_fn)(void *, const u16 *path, u32 line_offset);
struct m3u_stats { u32 accepted, skipped, invalid, limited; };
/* Single player-service owner; not reentrant. Scratch is in payload BSS. */
int m3u_scan(m3u_read_fn, m3u_entry_fn, void *ctx, const u16 *base,
             struct m3u_stats *stats);
int m3u_resolve(const u16 *base, const u8 *line, u32 len, u16 *out);
#endif
