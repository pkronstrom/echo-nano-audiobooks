/* MP3-only streaming adapter. Native ISR retains ownership of DMA scheduling. */
#include "speed.h"
#include "session.h"
#include "../experiments/audiobook_speed/speed.h"
#define WORD(a) (*(volatile u32 *)(a))
#define FRAMES 256u
#define CALLBACK 0x03072f5du
static u32 desired, launched, audio_channel;
static speed_state core;
/* Native conversion expands packed 16-bit stereo into 32-bit lanes in place. */
static u32 pcm[2][FRAMES*2];
static volatile u32 busy[2], playing;
static u32 playing_callback, raw_pointer, playing_channel;
static u32 epoch, slot_epoch[2], native_pointer, native_frames;
static volatile u32 transition;
static u32 next_slot, active, bypass, eof, finished, rate;
static const int16_t *input;
static u32 remaining, queued_ms, fraction, staged;
static volatile u32 audible_ms;
static u32 end_ms[2];
static uint64_t source_end;
u32 playback_speed_get(void){return desired>=4&&desired<=8?desired:4;}
void playback_speed_set(u32 q){if(q>=4&&q<=8)desired=q;}
static u32 lock(void){u32 p;__asm__ volatile("mrs %0,primask\ncpsid i":"=r"(p)::"memory");return p;}
static void unlock(u32 p){__asm__ volatile("msr primask,%0"::"r"(p):"memory");}
void playback_speed_reset(void)
{
    u32 mask=lock();epoch++;
    active=bypass=eof=finished=remaining=staged=0;input=0;
    next_slot=busy[0]?1:0;source_end=0;fraction=0;
    unlock(mask);
}
/* Only a successfully selected book starts a new preference lifetime. DSP
 * resets for seek, resume and chapter changes retain this launched rate. */
void playback_speed_launch(void)
{
    launched=playback_speed_get();
    playback_speed_reset();
}
static void wake(void){WORD(0xe000ed04)=1u<<28;}
/* Terminal errors discard unsubmitted output but never release live DMA. */
static void fault(void)
{
    u32 mask=lock();
    eof=finished=1;remaining=staged=0;input=0;
    for(u32 i=0;i<2;i++)if(playing!=i+1)busy[i]=0;
    WORD(0x0300d7f8)=1; /* Cancel native prepared handoff. */
    wake();unlock(mask);
}
/* Only a thread-mode startup boundary may retire a stopped transfer. An ISR
 * may already have snapshotted its callback even after the table was cleared. */
static void retire_stopped(void)
{
    u32 ipsr;__asm__ volatile("mrs %0,ipsr":"=r"(ipsr));
    if(ipsr || !playing || playing_channel>=6)return;
    u32 bit=1u<<playing_channel;
    if(WORD(0x600003a0)&bit)return;
    volatile u32 *callback=(volatile u32 *)(0x0300bd88+4*playing_channel);
    if(*callback && *callback!=CALLBACK)return;
    if(*callback==CALLBACK){
        *callback=0;WORD(0x60000338)=bit;
        __asm__ volatile("dsb":::"memory");
    }
    if(playing<=2)busy[playing-1]=0;
    playing=0;playing_callback=0;
}
static int native_capture(void **p,u32 *n)
{
    u32 codec=WORD(0x03039e94);
    if(codec==255)return -1;
    return ((int (*)(u32,void *,void *,u32))((u32 *)0x03035178)[codec])(10,p,n,0);
}
static int eligible(void)
{
    if(!playback_active || launched<=4 || WORD(0x03039e94)!=0 ||
       WORD(0x03039714)!=0x03023090 || WORD(0x0302312c)!=16)return 0;
    rate=WORD(0x03023098);
    return rate>=8000 && rate<=48000;
}
int playback_speed_capture(void **p,u32 *n,u32 caller)
{
    if(caller!=0x0306957f){
        u32 mask=lock();transition=1;
        /* Native stop/resume may already replace *p and clear its prepared
         * flag. Our unsubmitted slots still need release independently. */
        if(playing || busy[0] || busy[1])WORD(0x0300d7f8)=1;
        for(u32 i=0;i<2;i++)if(playing!=i+1)busy[i]=0;
        retire_stopped();
        if(playing==3){
            /* Startup ignores wait and clears *p. Give it the other native
             * buffer, and do not dispatch a codec delivery that can reuse DMA. */
            *p=(void *)(raw_pointer==0x03023174?0x0302c174:0x03023174);
            *n=128;WORD(0x0300d7f8)=1;
            playback_speed_reset();transition=0;unlock(mask);return 2;
        }
        /* Native resume ignores a wait result and clears/converts *p. Restore
         * its large native buffer before dispatch, never leave our small slot. */
        if(playback_speed_owns(*p)){
            *p=(void *)(native_pointer?native_pointer:0x03023174);
            *n=native_frames?native_frames:128;
        }
        playback_speed_reset();unlock(mask);
        int result=native_capture(p,n);
        if(result==1){native_pointer=(u32)*p;native_frames=*n;}
        transition=0;return result;
    }
    if(transition || playing==3)return 2; /* Native startup/preroll owns A/B. */
    if(!active && !bypass){if(!eligible())bypass=1;}
    if(finished)return busy[0]||busy[1]||playing?2:0;
    if(bypass)return native_capture(p,n);
    u32 slot=next_slot;
    if(busy[slot])return 2;
    u32 need_input=!active;
    for(u32 work=0;work<8;work++){
        if(need_input && !remaining && !eof){
            u32 mask=lock();
            u32 stamp=WORD(0x03039e20),count=WORD(0x03039e40),frames=0;
            void *buffer=0;
            /* Completion publishes this shadow through the host IRQ. A false
             * ready check stays false while calling the nonblocking wait/idle
             * path; a ready packet is stable until our next decode request. */
            if(WORD(0x03039e44)!=1){
                WORD(0x0300d800)=1;
                int pending=native_capture(&buffer,&frames);
                unlock(mask);
                if(pending==2)return 2;
                /* This branch cannot succeed for the audited native codec. */
                return pending;
            }
            unlock(mask);
            int status=native_capture(&buffer,&frames);
            if(status==2)return 2;
            if(status!=1){
                if(!active)return status;
                eof=1;
            }else{
                if((buffer!=(void *)0x03023174 && buffer!=(void *)0x0302c174) ||
                   !frames || frames>1152){
                    /* Unknown native contract: never feed unchecked memory to DSP. */
                    if(!active){bypass=1;*p=buffer;*n=frames;return 1;}
                    eof=1; /* Drain already accepted source, then native EOF. */
                }else{
                    native_pointer=(u32)buffer;native_frames=frames;
                    if(!active){
                        speed_init(&core,rate,2,launched);active=1;
                        u32 duration=(count && count<=1152?count:frames)*1000/rate;
                        queued_ms=audible_ms=stamp>duration?stamp-duration:0;
                    }
                    input=buffer;remaining=frames;
                }
            }
        }
        speed_result result;
        if(!staged)for(u32 i=0;i<FRAMES*2;i++)pcm[slot][i]=0;
        if(speed_process(&core,input,remaining,eof,
                         (int16_t *)pcm[slot]+staged*2,FRAMES-staged,&result)){
            fault();
            return busy[0]||busy[1]||playing?2:0;
        }
        if(result.consumed){input+=result.consumed*2;remaining-=result.consumed;}
        if(result.done)finished=1;
        staged+=result.produced;
        /* Keep partial PCM private across decoder waits/work-budget yields.
         * Native EQ and DMA scheduling receive full packets until the tail. */
        if(staged==FRAMES || (finished && staged)){
            /* Each <=256-frame packet represents <=512 source frames. */
            u32 delta=(u32)(result.source_end-source_end);
            source_end=result.source_end;
            u32 ticks=delta*1000+fraction;
            queued_ms+=ticks/rate;fraction=ticks%rate;
            end_ms[slot]=queued_ms;slot_epoch[slot]=epoch;busy[slot]=1;next_slot=slot^1;
            *p=pcm[slot];*n=staged;staged=0;return 1;
        }
        if(finished)return busy[0]||busy[1]?2:0;
        need_input=1;
    }
    /* No decoder interrupt is guaranteed after a CPU work-budget yield. */
    wake();return 2;
}
int playback_speed_dma(u32 c,void *p,u32 d,u32 n,const void *cfg,u32 cb)
{
    u32 slot=2, token=0;
    u32 audio=c==5 && d==0x40030024;
    if(audio){
        if(p==pcm[0])slot=0;
        else if(p==pcm[1])slot=1;
    }
    u32 mask=lock();
    if(audio && playing){
        /* Caller ignores submission failures. Drop only the rejected prepared
         * slot; the currently playing slot and callback remain authoritative. */
        fault();unlock(mask);return -1;
    }
    if(slot<2){token=slot+1;busy[slot]=1;}
    else if(audio && cb==0x030693cb && !bypass && eligible())token=3;
    if(token){playing=token;playing_callback=cb;raw_pointer=(u32)p;cb=CALLBACK;}
    /* Native DMA enters/exits a byte-counted critical section; its exit uses
     * CPSIE, ignoring incoming PRIMASK. Keep one native nesting level so it
     * cannot enable interrupts before ownership/failure bookkeeping completes. */
    volatile u8 *depth=(volatile u8 *)0x0300d83e;
    u32 nesting=*depth;
    int result=-1;
    if(nesting<254){
        *depth=nesting+1;
        result=FW(0x0306c1e4,int,u32,void *,u32,u32,const void *,u32)(c,p,d,n,cfg,cb);
        *depth=nesting;
    }
    if(result>=0 && audio)audio_channel=(u32)result+1;
    if(result>=0 && token)playing_channel=(u32)result;
    if(result<0 && token){
        playing=0;playing_callback=0;
        fault();
    }
    unlock(mask);return result;
}
void playback_speed_done(void)
{
    u32 slot=playing, callback=playing_callback;playing=0;playing_callback=0;
    if(slot && slot<=2){
        if(active && slot_epoch[slot-1]==epoch)audible_ms=end_ms[slot-1];
        busy[slot-1]=0;
    }
    if(callback)((void (*)(void))callback)();
    if(*(volatile u16 *)0x0300d7f0==0 && (active || slot))wake();
}
int playback_speed_position(u32 *ms)
{
    if(!active || !playback_active)return 0;
    *ms=audible_ms;return 1;
}
int playback_speed_seek(u32 ms,u32 flag)
{
    u32 owned=active || busy[0] || busy[1] || playing;
    transition=1;
    playback_speed_reset();
    u32 codec=WORD(0x03039e94);
    int result=codec==255?-1:((int (*)(u32,u32,u32,u32))((u32 *)0x03035178)[codec])(14,ms,flag,0);
    transition=0;if(owned)wake();return result;
}
int playback_speed_owns(void *p){return p==pcm[0] || p==pcm[1];}
int playback_speed_time(u32 *ms)
{
    u32 codec=WORD(0x03039e94);
    if(codec==255)return -1;
    int result=((int (*)(u32,void *,u32,u32))((u32 *)0x03035178)[codec])(7,ms,0,0);
    playback_speed_position(ms);
    return result;
}

/* UI queries must not mutate eligibility or the current source clock. */
int playback_speed_supported(void)
{
    u32 hz=WORD(0x03023098);
    return !(bypass && launched>4) && playback_active && WORD(0x03039e94)==0 &&
        WORD(0x03039714)==0x03023090 && WORD(0x0302312c)==16 && hz>=8000 && hz<=48000;
}
u32 playback_speed_actual(void)
{
    return playback_speed_supported() && launched>=4 && launched<=8?launched:4;
}
/* Called only after native pause. Never infer DMA completion from its bounded
 * channel5 wait: use the actual accepted channel, including native1x output.
 * Do not clear a foreign callback or retire from an interrupted ISR context. */
int playback_speed_drained(void)
{
    u32 mask=lock(),ipsr;__asm__ volatile("mrs %0,ipsr":"=r"(ipsr));
    int ready=0;
    if(ipsr || *(volatile u16 *)0x0300d7f0!=4 ||
       *(volatile u16 *)0x0300d81a!=3)goto out;
    if(audio_channel){
        if(audio_channel>6)goto out;
        u32 channel=audio_channel-1,bit=1u<<channel;
        volatile u32 *callback=(volatile u32 *)(0x0300bd88+4*channel);
        if(WORD(0x600003a0)&bit)goto out;
        if(*callback && *callback!=CALLBACK && *callback!=0x030693cb)goto out;
        if(*callback){*callback=0;WORD(0x60000338)=bit;__asm__ volatile("dsb":::"memory");}
    }
    retire_stopped();ready=!playing;
out:
    unlock(mask);return ready;
}
