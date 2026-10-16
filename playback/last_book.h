#ifndef ECHO_LAST_BOOK_H
#define ECHO_LAST_BOOK_H
#include "runtime.h"
/* Current payload lifetime: copied identity, never browser/decoder pointers. */
void last_book_label(u16 out[256]);
void last_book_remember(const u16 *path);
int last_book_get(u16 *out);
int last_book_snapshot(u16 *out,u32 *signature);
#endif
