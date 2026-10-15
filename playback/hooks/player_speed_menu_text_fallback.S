@ Invalid payload: never pass a synthetic ID to the native resource reader.
@ patch 32 0307cf98
#include "fw.inc"
    movw r3,#0xff00
    cmp r0,r3
    blo ordinary
    cmp r2,#2
    blo done
    movs r3,#0
    strh r3,[r1]
done:
    bx lr
ordinary:
    fb 0x03067860
    .org 28
