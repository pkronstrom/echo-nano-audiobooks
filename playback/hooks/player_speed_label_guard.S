@ patch 27 0307a2c8
@ Draw after the artist marquee update, also on incremental player paints.
#include "fw.inc"
#include "playback_syms.inc"
    push {r0,lr}
    fbl 0x03052fe4
    pop {r0,lr}
    push {r0,r1}
    ldr r0,=playback_speed_label+1
    adr r1,stock
    adds r1,#1
    fb 0x03072f62
stock:
    bx lr
    .ltorg
    .org 36
