@ patch 27 0307a014
@ Two adjacent filename printf strings; only their printf BLs are disabled.
#include "fw.inc"
#include "playback_syms.inc"
    ldr r0,=playback_header
    ldr r0,[r0]
    ldr r1,=0x32504e45
    cmp r0,r1
    bne stock
    ldr r0,=playback_feedback_bridge+1
    blx r0
stock:
    add sp,#36
    mov r0,r4
    pop {r4-r11,pc}
    .ltorg
    .org 36
