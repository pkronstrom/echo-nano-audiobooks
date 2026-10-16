@ patch 0 030733e0
@ Former SafePoweroff diagnostic; its sole module1 printf is disabled.
@ Every application boot invalidates retained payload before normal callbacks.
#include "fw.inc"
    push {r4-r9,lr}              @ Replay the original application-entry frame.
    push {r0,r1}
    ldr r0,=0x03092400
    movs r1,#0
    str r1,[r0]
    dsb
    isb
    pop {r0,r1}
    fb 0x030660ce
    .ltorg
    .org 32
