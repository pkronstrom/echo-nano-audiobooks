#ifndef ECHO_PLAYBACK_SESSION_H
#define ECHO_PLAYBACK_SESSION_H
#include "runtime.h"
extern u32 playback_active;
u32 playback_browser_select(u8 *extensions);
void playback_begin(const u16 *argument);
int playback_prepare(u32 mode);
int playback_queue_init(u8 *,u32,u32,u32,const char *);
int playback_advance(u8 *,int);
void playback_force_mode(void);
#endif
