@ patch 27 0307b1f4
@ Former display-mode diagnostic, disabled by checked integration.
#include "fw.inc"
#include "playback_syms.inc"
    push {r0,r1}
    ldr r0,=playback_book_screen+1
    adr r1,stock
    adds r1,#1
    fb 0x03072f62
stock:
    movs r0,#6
    fb 0x03051574
    .ltorg
    .org 36
