#ifndef ECHO_NAVIGATION_H
#define ECHO_NAVIGATION_H
#include "fw.h"
void navigation_menu_init(void);
u32 navigation_menu_dispatch(void);
void navigation_browser_init(void);
u32 navigation_event(u32 message);
extern u32 navigation_icons[8];
extern u32 navigation_count;
#endif
