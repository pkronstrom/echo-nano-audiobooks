#ifndef ECHO_BOOK_MENU_H
#define ECHO_BOOK_MENU_H
#include "runtime.h"
u16 *book_text(u16 *out,const char *value);
void book_mark_label(u16 *out,u32 index);
int book_menu_open_selected(void);
int book_menu_continue_last(void);
u32 book_menu_event(u32 message);
int book_menu_browser_init(void);
void book_menu_reset(void);
const char *playback_speed_label_text(u32 quarters);
#endif
