@ Tail of already reclaimed module23 function, after track_artists setup.
@ Background at9e40 and glyph at9e60; no reloadable payload dependency.
@ patch 23 03079e40
#include "fw.inc"
    push {r0,r2,r3,lr}
    fbl 0x030521d4
    pop {r0,r2,r3,lr}
    movs r1,#32
    fb 0x030521d4
    .org 32
    movs r1,#0
    fb 0x030521d4
    .org 48
