#ifndef ECHO_BOOK_PREVIEW_H
#define ECHO_BOOK_PREVIEW_H
#include "runtime.h"
/* Independent, read-only metadata for the book being browsed. Never selects
 * decoder state or changes the active queue/resume/bookmark companion. */
int book_preview_open(const u16 *path);
u32 book_preview_count(void);
int book_preview_ref(u32 index,struct media_ref *out);
u32 book_preview_signature(void);
u32 book_preview_resume(u32 *milliseconds);
int book_preview_mark(u32 index,u32 entry[2]);
u32 book_preview_marks(void);
int book_preview_delete(u32 index);
#endif
