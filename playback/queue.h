#ifndef ECHO_PLAYLIST_QUEUE_H
#define ECHO_PLAYLIST_QUEUE_H
#include "m3u.h"
#include "path.h"
#define PLAYLIST_CAPACITY 256
typedef int (*playlist_lookup_fn)(void *, const u16 *, struct media_ref *);
/* Separate narrow fields keep word geometry aligned without per-track padding.
 * Caller-owned contexts permit previewing another book without replacing playback.
 * Initialize with {0} or playlist_queue_clear before first access. Parsing itself
 * uses the shared M3U scratch buffer unless a private workspace is supplied. */
struct queued_file { u32 parent, length, cluster; };
struct playlist_queue {
    struct queued_file tracks[PLAYLIST_CAPACITY];
    u16 indices[PLAYLIST_CAPACITY];
    u8 flags[PLAYLIST_CAPACITY];
    u32 count, signature;
};
int playlist_queue_build(struct playlist_queue *, m3u_read_fn, playlist_lookup_fn,
                         void *, const u16 *, struct m3u_stats *);
int playlist_queue_build_with_workspace(struct playlist_queue *, struct m3u_workspace *,
                                        m3u_read_fn, playlist_lookup_fn, void *,
                                        const u16 *, struct m3u_stats *);
void playlist_queue_clear(struct playlist_queue *);
u32 playlist_queue_count(const struct playlist_queue *);
u32 playlist_queue_signature(const struct playlist_queue *);
int playlist_queue_ref(const struct playlist_queue *, u32, struct media_ref *);
/* Replaces queue. Returns accepted count, or negative error with empty queue. */
int playlist_build(m3u_read_fn, playlist_lookup_fn, void *, const u16 *, struct m3u_stats *);
void playlist_import(const struct playlist_queue *);
void playlist_clear(void);
u32 playlist_count(void);
/* Playlist bytes + accepted line offsets; independent of on-card clusters. */
u32 playlist_signature(void);
u32 playlist_physical_signature(void);
u32 playlist_queue_physical_signature(const struct playlist_queue *);
int playlist_ref(u32 index, struct media_ref *);
int playlist_audio_path(const u16 *);
#endif
