@ patch 0 03065918
@ Reclaimed watchdog printf string, no playback payload or RAM dependency.
#include "fw.inc"
    cmp r1,#0x40
    bne ordinary
    cmp r0,#14
    bne ordinary
    adds r0,#5
ordinary:
    adds r0,#1
    str r1,[r5,#48]
    fb 0x03065ec4
    .org 40
