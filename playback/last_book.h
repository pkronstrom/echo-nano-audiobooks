#ifndef ECHO_LAST_BOOK_H
#define ECHO_LAST_BOOK_H
#include "runtime.h"
/* Durable selection extension in existing CRC-covered RSM journal sectors. */
#define LAST_BOOK_TAG 0x31424c45u
extern u32 book_selection;
void last_book_restore(void);
struct content_root;
void last_book_restore_roots(const struct content_root *,u32);
void last_book_record(u32 sector[128]);
void last_book_label(u16 out[256]);
void book_path_title(const u16 *path,u16 *out,u32 capacity);
void last_book_remember(const u16 *path);
int last_book_get(u16 *out);
int last_book_snapshot(u16 *out,u32 *signature);
#endif
