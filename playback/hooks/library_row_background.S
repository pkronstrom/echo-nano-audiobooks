@ Native module22 helper: repeat the row resource to cover the removed icon area.
@ Data cave follows library_menu_42 restore and ends before menu state0x0300e8a8.
@ Keep image/y across a native draw that can clobber all argument registers.
@ patch 22 0300e788
#include "fw.inc"
    push {r0,r2,r3,lr}
    fbl 0x030521d4
    pop {r0,r2,r3,lr}
    movs r1,#32
    fb 0x030521d4
    .org 32
