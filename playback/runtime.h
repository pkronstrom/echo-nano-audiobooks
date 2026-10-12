#ifndef ECHO_PLAYBACK_RUNTIME_H
#define ECHO_PLAYBACK_RUNTIME_H
#include "path.h"
#include "m3u.h"
int playback_lookup(const u16 *, struct media_ref *);
int playback_open(const struct media_ref *);
int playback_read(int handle, u32 offset, u8 *out, u32 length);
void playback_close(int handle);
int playback_select_ref(const struct media_ref *, u8 *state, u32 position, u32 count);
int playback_load_playlist(const u16 *path, struct m3u_stats *);
int playback_playlist_step(u8 *state, int direction);
u32 playback_init(void);
#endif
