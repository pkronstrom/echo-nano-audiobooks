#ifndef ECHO_BOOK_RESUME_H
#define ECHO_BOOK_RESUME_H
#include "fw.h"
/* RSM word 8: SPD tag plus quarter-speed, covered by the sector CRC.
 * Legacy zero/unknown values restore 1x without invalidating saved position. */
#define BOOK_SPEED_TAG 0x53504400u
static inline u32 book_rate(u32 value)
{ return value>=BOOK_SPEED_TAG+4 && value<=BOOK_SPEED_TAG+8?value-BOOK_SPEED_TAG:4; }
u32 book_load(const u16 *playlist, u32 *milliseconds);
void book_save(void);
void book_autosave(void);
void book_clear(void);
u32 book_crc(const void *,u32);
#endif
