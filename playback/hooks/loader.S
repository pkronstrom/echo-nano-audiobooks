@ patch 0 03072e28
@ Experimental resident loader, not included in the delivery image.
@ Reclaims one 84-byte resident debug message; its sole printf call must be disabled.
#include "fw.inc"
#include "playback_syms.inc"
    push {r4, lr}
    ldr r4, =0x0309b694
    ldr r0, [r4]
    ldr r1, =0x32504e45
    cmp r0, r1
    beq success
    ldr r1, =0x0300d454
    ldr r1, [r1]
    ldr r0, =0x00a55000
    add r1, r0
    mov.w r0, #0x30000
    movw r2, #PLAYBACK_BYTES
    mov r3, r4
    fbl 0x0306b36c
    cbnz r0, failure
    dsb
    isb
    ldr r0, [r4]
    ldr r1, =0x32504e45
    cmp r0, r1
    bne failure
    fbl playback_init
success:
    movs r0, #0
    pop {r4, pc}
failure:
    movs r0, #0
    str r0, [r4]
    movs r0, #1
    pop {r4, pc}
    .ltorg
