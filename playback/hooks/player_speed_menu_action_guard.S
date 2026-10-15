@ Module32 diagnostic cave; shared resident ENP2 guard preserves original args.
@ patch 32 0307a79c
#include "fw.inc"
#include "playback_syms.inc"
    .equ PLAYER_SPEED_SHARED_GUARD, 0x03072f62
    push {r0,r1}
    ldr r0,=player_speed_menu_action+1
    ldr r1,=0x0307a7b5
    fb PLAYER_SPEED_SHARED_GUARD
    .ltorg
    .org 24
    movw r3,#0xff00
    cmp r0,r3
    blo ordinary
    movs r0,#0
    bx lr
ordinary:
    fb 0x03079fbc
    .org 48
