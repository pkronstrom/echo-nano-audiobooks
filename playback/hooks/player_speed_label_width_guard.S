@ patch 27 0307a39c
@ Former LRC diagnostic; its printf is disabled by checked integration.
#include "fw.inc"
#include "playback_syms.inc"
    ldr r0,=playback_header
    ldr r0,[r0]
    ldr r1,=0x32504e45
    cmp r0,r1
    bne stock
    ldr r0,=playback_active
    ldr r0,[r0]
    cmp r0,#1
    ite eq
    moveq r0,#86
    movne r0,#107
    b done
stock:
    movs r0,#107
done:
    strh r0,[sp,#60]
    fb 0x0307adee
    .ltorg
    .org 56
