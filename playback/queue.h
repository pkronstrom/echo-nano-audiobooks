#ifndef ECHO_PLAYLIST_QUEUE_H
#define ECHO_PLAYLIST_QUEUE_H
#include "m3u.h"
#include "path.h"
#define PLAYLIST_CAPACITY 256
typedef int (*playlist_lookup_fn)(void *, const u16 *, struct media_ref *);
/* Replaces queue. Returns accepted count, or negative error with empty queue. */
int playlist_build(m3u_read_fn, playlist_lookup_fn, void *, const u16 *, struct m3u_stats *);
void playlist_clear(void);
u32 playlist_count(void);
int playlist_ref(u32 index, struct media_ref *);
int playlist_audio_path(const u16 *);
#endif
