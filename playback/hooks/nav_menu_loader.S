@ patch 21 03079600
#include "fw.inc"
#include "playback_syms.inc"
    push {r0-r3,r12,lr}
    fbl 0x03072e28
    cbnz r0,1f
    fbl navigation_menu_init
1:  pop {r0-r3,r12,lr}
    movs r1,#100
    strh r1,[r0,#28]
    bx lr
