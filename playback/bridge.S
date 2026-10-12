.syntax unified
.thumb
.text
.macro jump address
    ldr ip, =\address + 1
    bx ip
.endm
.macro entry name
    .global \name
    .thumb_func
\name:
.endm
entry playback_launch_bridge
    movs r0, #1
    strh r0, [sp, #48]
    movs r2, #128
    ldr r1, =0x0300d492
    movs r0, #3
    ldr ip, =0x03067861
    blx ip
    ldr r5, =0x0300d164
    ldr r8, =0x0300d85c
    ldr r10, =0x0300ec1c
    mov.w r9, #0
    jump 0x0307b0b2
entry playback_queue_bridge
    push {r4,lr}
    ldr r4, [sp,#8]
    sub sp,#8
    str r4, [sp]
    bl playback_queue_init
    add sp,#8
    pop {r4,lr}
    cmp r0,#0
    beq 1f
    jump 0x03082978
1:  bx lr
entry playback_advance_bridge
    push {r4,lr}
    bl playback_advance
    ldr r1, =playback_active
    ldr r1, [r1]
    cmp r1,#0
    beq 1f
    cmp r0,#0
    beq 1f
    pop {r4,lr}
    ldr r5, =0x03039708
    jump 0x030819b8
1:  pop {r4,pc}
entry playback_settings_bridge
    ldr r1, [r5,#12]
    ldrb.w r0, [r7,#0x6d]
    bic r0,r0,#4
    str r0,[r1,#28]
    movs r0,#2
    str r0,[r1,#36]
    strh.w r0,[r10,#10]
    bl playback_force_mode
    ldrh.w r8,[r10,#2]
    strh.w r8,[r10,#6]
    jump 0x0308319c

entry playback_save_close_bridge
    push {r0-r3,r12,lr}
    bl book_save
    pop {r0-r3,r12,lr}
    jump 0x03084e28
entry playback_stock_save_bridge
    push {r4,r5,r6,lr}
    mov r4,r1
    ldrh r5,[r4,#2]
    ldr ip,=0x03085001
    blx ip
    ldr r1,=playback_active
    ldr r1,[r1]
    cbz r1,1f
    strh r5,[r4,#2]
1:  pop {r4,r5,r6,pc}
entry playback_init_scope_bridge
    ldrh.w r0,[r8,#0xf2]
    cmp r0,#99
    bne 1f
    ldr r0,[r4,#28]
    bic r0,r0,#4
    str r0,[r4,#28]
    jump 0x0308298a
1:  ldr r0,[r4,#28]
    cmp r0,#2
    jump 0x03082966
entry playback_advance_scope_bridge
    ldr r2,=0x0300d85c
    ldrh.w r1,[r2,#0xf2]
    cmp r1,#99
    mov.w r1,#3
    it eq
    moveq r1,#2
    jump 0x03081848
entry playback_order_bridge
    ldrb.w r0,[r7,#0x6f]
    ldr ip,=playback_active
    ldr ip,[ip]
    cmp ip,#0
    it ne
    movne r0,#0
    jump 0x030831be
