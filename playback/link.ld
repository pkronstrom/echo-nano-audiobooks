/* Playback shares the upper module40 sort-buffer range with refresh.
 * All other nonempty module code/data/BSS ends below 0x03092400.
 * Image staging verifies those bounds against the pinned stock table.
 * No playback hook may remain installed while the refresh blob is active. */
MEMORY { RAM (rwx) : ORIGIN = 0x03092400, LENGTH = 0x0309fff0 - 0x03092400 }
ENTRY(playback_init)
SECTIONS {
    .text : {
        KEEP(*(.header))
        *(.text*) *(.rodata*) *(.data*)
        . = ALIGN(8);
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
ASSERT(SIZEOF(.text) <= 0x6e00, "playback code exceeds verified refresh staging buffer")
ASSERT(__play_bss_end <= 0x0309fff0, "playback code/state exceeds reserved RAM")
