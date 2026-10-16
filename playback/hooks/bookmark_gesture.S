@ patch 0 03052d68
@ Reclaims the 51-byte out-of-bounds draw diagnostic; its tail printf is disabled.
#include "fw.inc"
#include "playback_syms.inc"
    ldr r2,=playback_header
    ldr r2,[r2]
    ldr r1,=0x32504e45
    cmp r2,r1
    bne stock
    ldr r2,=playback_active
    ldr r2,[r2]
    cmp r2,#1
    bne stock
    fb playback_bookmark_bridge
    @ Consume the favorite action, including a failed bookmark save. Never
    @ silently add an audiobook chapter to music Favorites on an I/O failure.
stock:
    fb 0x030686e0
    .ltorg
    .org 48
