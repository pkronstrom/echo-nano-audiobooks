@ patch 33 0308301e
#include "fw.inc"
#include "playback_syms.inc"
    fb playback_settings_bridge
    nop
    .org 0x03083024-PATCH_BASE
    push {r0-r3,r12,lr}
    fbl 0x03072e28
    cbnz r0, 2f
    ldr r0,[sp]
    fbl playback_begin
    pop {r0-r3,r12,lr}
    push {r4-r11,lr}
    fb 0x030827be
2:  movs r0,#245
    fbl msg_post
    pop {r0-r3,r12,lr}
    bx lr
    .org 0x03083060-PATCH_BASE
    fb playback_init_scope_bridge
    push {r0,r1}
    movw r0,#(playback_header & 0xffff)
    movt r0,#(playback_header >> 16)
    ldr r0,[r0]
    movw r1,#0x4e45
    movt r1,#0x3250
    cmp r0,r1
    pop {r0,r1}
    fbeq playback_save_close_bridge
    fb 0x03084e28
    .org 0x03083084-PATCH_BASE
    movw r2,#(playback_header & 0xffff)
    movt r2,#(playback_header >> 16)
    ldr r2,[r2]
    movw r3,#0x4e45
    movt r3,#0x3250
    cmp r2,r3
    fbeq playback_bookmark_poll
    fb 0x0306b05c
    .org 0x030830a0-PATCH_BASE
    fb playback_advance_scope_bridge
    push {r0,r1}
    movw r0,#(playback_header & 0xffff)
    movt r0,#(playback_header >> 16)
    ldr r0,[r0]
    movw r1,#0x4e45
    movt r1,#0x3250
    cmp r0,r1
    pop {r0,r1}
    fbeq playback_stock_save_bridge
    fb 0x03085000
    .org 0x030830dc-PATCH_BASE
