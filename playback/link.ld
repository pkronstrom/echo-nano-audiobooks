/* Playback and refresh are mutually exclusive owners of this RAM.
 * No playback hook may remain installed while the refresh blob is active. */
MEMORY { RAM (rwx) : ORIGIN = 0x0309b694, LENGTH = 0x0309fff0 - 0x0309b694 }
ENTRY(playback_init)
SECTIONS {
    .text : {
        KEEP(*(.header))
        *(.text*) *(.rodata*) *(.data*)
        . = ALIGN(4);
        __play_code_end = .;
    } > RAM
    .bss (NOLOAD) : ALIGN(4) {
        __play_bss_start = .;
        *(.bss*) *(COMMON)
        . = ALIGN(4);
        __play_bss_end = .;
    } > RAM
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.attributes) *(.comment) *(.note*) }
}
ASSERT(SIZEOF(.text) <= 0x2e00, "playback code exceeds verified firmware padding")
ASSERT(__play_bss_end <= 0x0309fff0, "playback code/state exceeds reserved RAM")
