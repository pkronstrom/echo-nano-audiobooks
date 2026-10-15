@ Native module32 list layout; no payload dependency.
@ patch 32 0307973c
#include "fw.inc"
    push {r0,r2,r3,lr}
    movs r1,#0
    fbl 0x030521d4
    pop {r0,r2,r3,lr}
    movs r1,#32
    fb 0x030521d4
    .org 24
