@ patch 33 0308301e
@ P1b: raw File Browser always stays in its selected folder. Replace its mode
@ transition block, and reuse the displaced code region for two tiny helpers.
@ No other genuine code branch targets the removed interior. Type10 keeps the
@ original separate block at30dc; the original external entry is3016 ->301e.
#include "fw.inc"
    ldr r1, [r5, #12]
    ldrb.w r0, [r7, #0x6d]
    bic r0, r0, #4              @ clear folder jumping in active mode only
    str r0, [r1, #28]
    movs r0, #2
    str r0, [r1, #36]
    strh.w r0, [r10, #10]
    ldrh.w r8, [r10, #2]
    strh.w r8, [r10, #6]
    fb 0x0308319c

    .org 0x03083060 - PATCH_BASE
@ Called by branch from MusicInit2962, shared by initial playback and resume.
    ldrh.w r0, [r8, #0xf2]
    cmp r0, #99
    bne 1f
    ldr r0, [r4, #28]
    bic r0, r0, #4
    str r0, [r4, #28]
    fb 0x0308298a               @ scope2; queue builder recalculates local count
1:  ldr r0, [r4, #28]
    cmp r0, #2                 @ flags consumed by stock IT at2966
    fb 0x03082966

    .org 0x030830a0 - PATCH_BASE
@ Called by branch from track advancement1844. Preserve r0 (signed direction).
    movw r2, #0xd85c
    movt r2, #0x0300
    ldrh.w r1, [r2, #0xf2]
    cmp r1, #99
    mov.w r1, #3
    it eq
    moveq r1, #2
    fb 0x03081848               @ write scope and continue stock next-track path
    .org 0x030830dc - PATCH_BASE
