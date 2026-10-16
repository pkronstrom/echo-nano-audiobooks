#include "fw.h"
#include "browser_playback.h"
extern void browser_book_event_bridge(void);

/* Fixed entry called by the unchanged-size native browser loader stub. The
 * resident initializer installs its own event branch, so replace it afterward.
 * No pointer from the player/resident payload retains this overlay entry. */
__attribute__((section(".book_init"),used))
void browser_book_init(void)
{
    FW(BOOK_NAV_INIT_ADDR,void,void)();
    const u32 address=0x0307b31a;
    u32 off=(((u32)browser_book_event_bridge)&~1u)-address-4,sign=(off>>24)&1;
    volatile u16 *p=(volatile u16 *)address;
    p[0]=0xf000|(sign<<10)|((off>>12)&0x3ff);
    p[1]=0x9000|((~((off>>23)^sign)&1)<<13)|((~((off>>22)^sign)&1)<<11)|((off>>1)&0x7ff);
    p[2]=0xbf00;
    __asm volatile("dsb\nisb" ::: "memory");
}
