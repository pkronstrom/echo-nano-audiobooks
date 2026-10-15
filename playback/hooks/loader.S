@ patch 0 03072e28
@ Resident loader used by the audiobook image.
@ Reclaims one 84-byte resident debug message; its sole printf call must be disabled.
#include "fw.inc"
#include "playback_syms.inc"
    push {r4, lr}
    ldr r4, =playback_header
    ldr r0, [r4]
    ldr r1, =0x32504e45
    cmp r0, r1
    beq success
    ldr r1, =0x0300d454
    ldr r1, [r1]
    ldr r0, playback_flash_offset
    add r1, r0
    mov.w r0, #0x30000
    @ Stock fw_read advances only one sector after an aligned bulk read.
    @ A partial tail would come from the wrong sector. Read whole sectors;
    @ the checked padding lands in payload BSS, cleared by playback_init.
    movw r2, #((PLAYBACK_BYTES + 511) & ~511)
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

playback_flash_offset:
    .word PLAYBACK_FLASH_OFFSET
