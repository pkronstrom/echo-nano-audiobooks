#ifndef ECHO_JOURNAL_H
#define ECHO_JOURNAL_H
#include "runtime.h"
#define JOURNAL_RESUME_MAGIC 0x31524e45u
#define JOURNAL_BOOKMARK_MAGIC 0x31424e45u
#define JOURNAL_BOOKMARK_CAPACITY 60u
/* Only journal_read_sector requires player-owned shared scratch. Open and the
 * nonblocking writer guard also support UI callers with independent buffers. */
int journal_sector_valid(const u32 *sector,u32 magic);
int journal_try_write(void);
void journal_end_write(void);
int journal_read_sector(int handle,u32 slot);
int journal_open(const u16 *playlist,const char *extension,struct media_ref *ref);
#endif
