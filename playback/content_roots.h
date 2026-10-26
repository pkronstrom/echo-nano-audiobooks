#ifndef ECHO_CONTENT_ROOTS_H
#define ECHO_CONTENT_ROOTS_H
#include "path.h"
#define CONTENT_ROOT_MAX 8
#define CONTENT_DEPTH_MAX 7
#define CONTENT_AUDIOBOOK 1
#define CONTENT_MEDITATION 2
struct content_root {
    u32 cluster[CONTENT_DEPTH_MAX];
    /* The scan consumes at most65536 raw entries across all directories. */
    u16 index[CONTENT_DEPTH_MAX];
    u8 depth, kind;
};
/* Physical DFS; root depth zero denotes the card root. Returns count, -1 on
 * capacity/work limit, -2 on I/O. Discard all output on error. */
int content_scan(media_read_fn, void *, int exfat, struct content_root *, u32 capacity);
typedef int (*content_visit_fn)(void *, const struct content_root *, const struct media_ref *);
int content_walk(media_read_fn, void *, int, const struct content_root *, content_visit_fn, void *);
/* Revalidate each ancestor by physical entry index and cluster. Returns 1 or
 * zero for stale/invalid ancestry, -2 on I/O. Caller rescans markers separately. */
int content_root_chain(media_read_fn, void *, int exfat,
                       const struct content_root *, struct media_ref out[7]);
#endif
