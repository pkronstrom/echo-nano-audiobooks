@ patch 0 030696d4
#include "fw.inc"
#include "playback_syms.inc"
    bne nonzero
    fb 0x03069562
nonzero:
    push {r0,r1}
    ldr r0,=playback_header
    ldr r0,[r0]
    ldr r1,=0x32504e45
    cmp r0,r1
    bne native
    pop {r0,r1}
    cmp r0,#0 @ Restore flags from the original comparison at 0306955c.
    fb playback_speed_status_bridge
native:
    pop {r0,r1}
    cmp r0,#0
    fb 0x030697e2
    .ltorg
    .org 56
