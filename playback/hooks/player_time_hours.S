@ patch 27 0307ab7e
@ Replace the native time painter (which discarded its hours argument).
@ Native caller converts u32 milliseconds: hours are bounded to 1193.
@ Compact 3x5 digits occupy x10..46, y25..29; full u32-ms range fits.
#include "fw.inc"
    push {r4-r7,lr}
    sub sp,#12 @ Align SP to 8 bytes after the five-register push.
    mov r4,r0
    mov r5,r1
    mov r6,r2
    movw r7,#0x7dbd
    movt r7,#0x0300
    movs r0,#0
    movs r1,#38
clear:
    strb r0,[r7]
    adds r7,#5
    subs r1,#1
    bne clear
    movw r7,#0x7dbd
    movt r7,#0x0300
    cbz r4,minutes
    mov r0,r4
    bl number
    bl colon
minutes:
    mov r4,r6
    mov r0,r5
    bl pair
    bl colon
    mov r0,r4
    bl pair
    add sp,#12
    pop {r4-r7,lr}
    movs r0,#6
    fb 0x03051524
number:
    push {r4,lr}
    movs r1,#10
    udiv r2,r0,r1
    mls r4,r2,r1,r0
    cbz r2,last
    mov r0,r2
    bl number
last:
    mov r0,r4
    bl digit
    pop {r4,pc}
pair:
    push {r4,lr}
    movs r1,#10
    udiv r2,r0,r1
    mls r4,r2,r1,r0
    mov r0,r2
    bl digit
    mov r0,r4
    bl digit
    pop {r4,pc}
colon:
    movs r0,#0x28
    strb r0,[r7]
    adds r7,#10
    bx lr
digit:
    movw r1,#:lower16:font
    movt r1,#:upper16:font
    add r0,r0,r0,lsl #1
    adds r1,r0
    movs r2,#3
column:
    ldrb r0,[r1],#1
    lsls r0,#1
    strb r0,[r7]
    adds r7,#5
    subs r2,#1
    bne column
    adds r7,#5
    bx lr
    .balign 2
font:
    .byte 31,17,31, 18,31,16, 29,21,23, 21,21,31, 7,4,31
    .byte 23,21,29, 31,21,29, 1,1,31, 31,21,31, 23,21,31
    .org 222
