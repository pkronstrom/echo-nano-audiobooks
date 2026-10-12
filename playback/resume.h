#ifndef ECHO_BOOK_RESUME_H
#define ECHO_BOOK_RESUME_H
#include "fw.h"
u32 book_load(const u16 *playlist, u32 *milliseconds);
void book_save(void);
void book_clear(void);
u32 book_crc(const void *,u32);
#endif
