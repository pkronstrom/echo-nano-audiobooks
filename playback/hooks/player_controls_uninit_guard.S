@ patch 27 0307a270
@ Reclaimed LRC size diagnostic; stock uninit is the unloaded-payload fallback.
#include "fw.inc"
#include "playback_syms.inc"
    push {r0,r1}
    ldr r0,=playback_player_uninit+1
    ldr r1,=0x03079513
    fb 0x03072f62
    .ltorg
    .org 44
