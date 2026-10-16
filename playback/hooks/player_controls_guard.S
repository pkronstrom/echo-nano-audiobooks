@ patch 27 0307a3d4
@ Reclaimed LRC completion diagnostic; native decoding remains the fallback.
#include "fw.inc"
#include "playback_syms.inc"
    push {r0,r1}
    ldr r0,=playback_player_key+1
    ldr r1,=0x03063243
    fb 0x03072f62
    .ltorg
    .org 36
