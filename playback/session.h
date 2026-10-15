#ifndef ECHO_PLAYBACK_SESSION_H
#define ECHO_PLAYBACK_SESSION_H
#include "runtime.h"
extern u32 playback_active;
u32 playback_music_request(void);
void playback_music_launch(void);
const u8 *playback_browser_selected_m3u(void);
const u8 *playback_browser_selected_node(void);
void playback_launch_override(u32 chapter,u32 milliseconds,u32 signature);
int playback_launch_path(const u16 *path,u32 chapter,u32 milliseconds,u32 signature);
void playback_launch_cancel(void);
u32 playback_browser_select(u8 *extensions);
void playback_begin(const u16 *argument);
int playback_prepare(u32 mode);
int playback_queue_init(u8 *,u32,u32,u32,const char *);
int playback_advance(u8 *,int);
void playback_force_mode(void);
u32 playback_position(struct media_ref *,u32 *milliseconds);
int playback_add_bookmark(void);
void playback_cancel_bookmark(void);
int playback_request_bookmark(void);
u32 playback_bookmark_poll(u32 message);
/* Live speed: request/poll return 0 idle, 1 draining, 2 launching, 3 done,
 * or -1 refused/failed. Refusal before pause leaves audio untouched. A failed
 * drain remains paused; cancel never resumes or resets outstanding DMA.
 * Call poll while draining; the 201st poll fails (a call budget, not a timer).
 * Completed preflight is repeated after drain. Post-handoff I/O failure cannot
 * resurrect a closed decoder; desired/latched rates roll back and status fails.
 * A completed restart uses native seek granularity, not sample-exact timing. */
int playback_rate_request(u32 quarters);
int playback_rate_poll(void);
void playback_rate_cancel(void);
#endif
