@ patch 0 03072f54
@ Resident DMA guard entry +0; completion guard entry +8 (Thumb 03072f5d).
@ Preserve all six AAPCS arguments, callee-saved registers and original LR.
#include "fw.inc"
#include "playback_syms.inc"
    push {r0,r1}
    ldr r0,=playback_speed_dma+1
    ldr r1,=0x0306c1e5
    b check
done:
    push {r0,r1}
    ldr r0,=playback_speed_done+1
    ldr r1,=0x030693cb
check:
    push {r4,r5}
    ldr r4,=playback_header
    ldr r4,[r4]
    ldr r5,=0x32504e45
    cmp r4,r5
    it ne
    movne r0,r1
    mov ip,r0
    pop {r4,r5}
    pop {r0,r1}
    bx ip
    .ltorg
    .org 64
