    .syntax unified
    .thumb
    .section .header, "a"
    .global playback_header
playback_header:
    .word 0x32504e45
    .word playback_init
    .word __play_bss_start
    .word __play_bss_end
