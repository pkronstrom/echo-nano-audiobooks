.syntax unified
.thumb
.section .text
.global browser_sort_native_count
.thumb_func
browser_sort_native_count:
    push {r4,r5,r6,lr}
    mov r4,r1
    b.w 0x03079752
.global browser_sort_select_bridge
.thumb_func
browser_sort_select_bridge:
    mov r0,r4
    bl browser_sort_select
    cmp r0,#0
    beq 1f
    cmp r0,#2
    beq 2f
    ldrb.w r5,[r4,#78]
    b.w 0x0307acfc
1:  b.w 0x0307af40

2:  b.w 0x0307b076
