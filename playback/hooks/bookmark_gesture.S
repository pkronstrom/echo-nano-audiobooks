@ patch 0 03052d68
@ Reclaims the 51-byte out-of-bounds draw diagnostic; its tail printf is disabled.
#include "fw.inc"
#include "playback_syms.inc"
    push {r4,lr}
    ldr r2,=playback_header
    ldr r2,[r2]
    ldr r1,=0x32504e45
    cmp r2,r1
    bne stock
    ldr r2,=playback_active
    ldr r2,[r2]
    cbz r2,stock
    fbl playback_request_bookmark
    pop {r4,lr}
    @ Consume the favorite action, including a failed bookmark save. Never
    @ silently add an audiobook chapter to music Favorites on an I/O failure.
    fb 0x030638ea
stock:
    fbl 0x030686e0
    pop {r4,pc}
    .ltorg
    .org 48
