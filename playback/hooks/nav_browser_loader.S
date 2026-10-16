@ patch 31 0307afa0
@ Audio whitelist's only ADR was replaced by the existing browser hook.
#include "fw.inc"
    push {r0-r3,r12,lr}
    fbl 0x03072e28
    cbnz r0,1f
    fbl 0x0307b884 @ fixed cold init, calls the SHA-bound resident init first
1:  pop {r0-r3,r12,lr}
    movs r1,#100
    strh r1,[r0,#28]
    bx lr
