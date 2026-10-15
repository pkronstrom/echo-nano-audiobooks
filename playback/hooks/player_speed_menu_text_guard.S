@ Module32 diagnostic cave; shared resident ENP2 guard preserves original args.
@ patch 32 03079ed0
#include "fw.inc"
#include "playback_syms.inc"
    .equ PLAYER_SPEED_SHARED_GUARD, 0x03072f62
    push {r0,r1}
    ldr r0,=player_speed_menu_text+1
    ldr r1,=0x0307cf99
    fb PLAYER_SPEED_SHARED_GUARD
    .ltorg
    .org 32
