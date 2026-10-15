#ifndef ECHO_PLAYBACK_SPEED_H
#define ECHO_PLAYBACK_SPEED_H
#include "runtime.h"
u32 playback_speed_get(void);
void playback_speed_set(u32 quarters);
void playback_speed_reset(void);
void playback_speed_launch(void);
int playback_speed_capture(void **buffer,u32 *frames,u32 caller);
int playback_speed_dma(u32 channel,void *buffer,u32 destination,u32 words,const void *config,u32 callback);
void playback_speed_done(void);
int playback_speed_position(u32 *milliseconds);
int playback_speed_owns(void *buffer);
int playback_speed_supported(void);
u32 playback_speed_actual(void);
int playback_speed_drained(void);
#endif
