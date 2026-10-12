#ifndef MUSIC_FILTER_H
#define MUSIC_FILTER_H
#include "fw.h"
extern u32 music_filter_errors;
void music_filter_reset(void);
int music_fat_entry(u8 *, u32, u32);
int music_exfat_entry(u8 *, const void *, u32);
int music_fat_original(u8 *, u32, u32);
int music_exfat_original(u8 *, const void *, u32);
void music_watchdog(void);
#endif
