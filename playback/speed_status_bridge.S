.syntax unified
.cpu cortex-m3
.thumb
.text
.global playback_speed_status_bridge
.type playback_speed_status_bridge,%function
.thumb_func
playback_speed_status_bridge:
    push {r0-r3,r12,lr}
    mrs r0,APSR
    push {r0,r4}
    ldr r0,[r7,#12]
    bl playback_speed_owns
    cbz r0,native
    pop {r0,r4}
    msr APSR_nzcvq,r0
    pop {r0-r3,r12,lr}
    b.w 0x030695e8
native:
    pop {r0,r4}
    msr APSR_nzcvq,r0
    pop {r0-r3,r12,lr}
    b.w 0x030697e2
.size playback_speed_status_bridge,.-playback_speed_status_bridge
