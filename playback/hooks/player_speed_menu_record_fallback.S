@ Invalid payload: native IDs still load; synthetic records become empty.
@ patch 32 0307cd64
#include "fw.inc"
    movw r3,#0xff00
    cmp r0,r3
    blo ordinary
    mov r0,r1
    movs r1,#58
    fb 0x030579a8
ordinary:
    fb 0x03067988
    .org 24
