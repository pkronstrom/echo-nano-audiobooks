#ifndef ECHO_BROWSER_PATH_H
#define ECHO_BROWSER_PATH_H
#include "path.h"
/* Audited mod31 layout: browser >=462 bytes, node624; output256 UTF16 units.
 * Single player-service owner. Returns1 only after verifying physical identity. */
int media_browser_path(media_read_fn, void *, int exfat, const u8 *browser,
                        const u8 *node, u32 root_cluster, u16 *out);
#endif
