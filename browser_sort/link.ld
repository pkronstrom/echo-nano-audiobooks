/* Browser-only extension loaded by native module31; never resident/player code. */
MEMORY { BROWSER (rwx) : ORIGIN = 0x0307b874, LENGTH = 0x03080470 - 0x0307b874 }
ENTRY(browser_sort_enumerate)
SECTIONS {
    .text : {
        KEEP(*(.header))
        *(.text*) *(.rodata*) *(.data*)
        __sort_metadata_start = .;
        KEEP(*(.sort_metadata))
        __sort_metadata_end = .;
        . = ALIGN(4);
        __sort_code_end = .;
    } > BROWSER
    .bss (NOLOAD) : ALIGN(8) {
        __sort_bss_start = .;
        *(.bss*) *(COMMON)
        . = ALIGN(8);
        __sort_bss_end = .;
    } > BROWSER
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.attributes) *(.comment) *(.note*) }
}
ASSERT(SIZEOF(.text) <= 4332, "browser sort code exceeds verified flash tail")
ASSERT(__sort_bss_end <= 0x03080470, "browser sort state overlaps native decoder")
ASSERT(__sort_metadata_end - __sort_metadata_start >= 4, "browser sort copied reset metadata missing")
