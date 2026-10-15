#ifndef ECHO_BOOKMARKS_H
#define ECHO_BOOKMARKS_H
#include "fw.h"
/* ENB1 companion, 60 manual chapter/time marks, independent of resume.
 * All APIs run on the player service, outside playlist parsing.
 * open returns count or -1; get returns 1 or -1. change returns new count
 * or -1 without evicting entries. index=~0 appends; chapter=0 deletes index. */
void bookmarks_clear(void);
int bookmarks_open(const u16 *playlist,u32 signature);
int bookmarks_get(u32 index,u32 entry[2]);
int bookmarks_change(u32 index,u32 chapter,u32 milliseconds);
#endif
