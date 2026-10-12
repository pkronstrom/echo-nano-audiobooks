#ifndef ECHO_PATH_H
#define ECHO_PATH_H
#include "fw.h"
struct media_dir { u32 cluster, length, index, flags; };
struct media_ref {
    struct media_dir parent;
    u32 index, cluster, size;
    u8 flags, attrs, filesystem, name_units;
};
typedef int (*media_read_fn)(void *ctx, int exfat, struct media_dir *parent,
                            u32 index, u8 *entry);
/* Absolute normalized UTF-16 path. 1 found, 0 missing, negative invalid/I/O.
 * Reads the physical filesystem, so deliberate access can include .nomusic. */
int media_resolve(media_read_fn read, void *ctx, int exfat,
                  const u16 *path, struct media_ref *out);
/* Recover a child directory name by physical identity. name has 256 u16 slots. */
int media_directory_name(media_read_fn, void *, int exfat, struct media_dir *,
                          u32 child, u16 *name, struct media_ref *);
#endif
