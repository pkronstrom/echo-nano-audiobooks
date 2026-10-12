#include "session.h"
#include "queue.h"
#include "resume.h"
#define STATE ((u8 *)0x0300d85c)
#define SERVICE ((u32 *)0x03039708)
#define PLAYER ((u32 *)0x03023090)
static u16 pending_path[256];
static u32 pending, starting, resume_position, resume_ms;
u32 playback_active;
static u16 half(const u8 *p) { return p[0] | (u16)p[1]<<8; }
static u32 word(const u8 *p) { return half(p) | (u32)half(p+2)<<16; }
static int m3u_name(const u8 *node)
{
    u32 n=0;
    while (n<256 && half(node+0x70+n*2)) n++;
    return n>=5 && n<256 && half(node+0x70+(n-4)*2)=='.' &&
           (half(node+0x70+(n-3)*2)|32)=='m' &&
           half(node+0x70+(n-2)*2)=='3' &&
           (half(node+0x70+(n-1)*2)|32)=='u';
}
/* Return selected node; low bit marks a captured playlist launch. No queue is
 * replaced while browsing folders. Copy the stock local audio whitelist too. */
u32 playback_browser_select(u8 *extensions)
{
    __builtin_memcpy(extensions,(const void *)0x0307afa0,44);
    const u8 *browser=(const u8 *)0x03005f6c;
    u32 selected=half(browser+0x1ee), address=word(browser);
    if (selected>1) return 0;
    for (u32 i=0;i<=selected;i++) {
        if (address!=0x0300e73c && address!=0x0300e9ac) return 0;
        if (i<selected) address=word((const u8 *)address+4);
    }
    const u8 *node=(const u8 *)address;
    if (half((const u8 *)0x0300ec1c+8)==3 && m3u_name(node)) {
        pending=0;
        if (!playback_browser_path(node,pending_path)) return 0;
        pending=1;
        return address|1;
    }
    if (node[0x4e]) pending=0; /* a deliberate ordinary-file selection */
    return address;
}
void playback_begin(const u16 *argument)
{
    /* Null means reopening current context; non-null launches a selection. */
    if (!pending && (argument || half(STATE+0xf2)!=99)) { playback_active=0; book_clear(); }
}
int playback_prepare(u32 mode)
{
    if (pending) {
        struct m3u_stats stats;
        pending=0; playback_active=0;
        int count=playback_load_playlist(pending_path,&stats);
        if (count<=0) {
            FW(0x0306b040,void,u32)(245);
            return 1;
        }
        resume_position=book_load(pending_path,&resume_ms);
        playback_active=1; starting=1;
    }
    if (playback_active) return 0;
    return FW(0x03082732,int,u32)(mode);
}
void playback_force_mode(void)
{
    if (playback_active) {
        PLAYER[7]=2; PLAYER[8]=0; PLAYER[9]=2;
        ((u16 *)STATE)[5]=2; ((u16 *)STATE)[6]=0;
    }
}
int playback_queue_init(u8 *state,u32 index,u32 scope,u32 order,const char *extensions)
{
    if (!playback_active) {
        FW(0x030603d0,int,u8 *,u32,u32,u32,const char *)(state,index,scope,order,extensions);
        return 0; /* stock caller ignores its original status */
    }
    playback_force_mode();
    if (starting) {
        starting=0;
        struct media_ref ref;
        if (resume_position && playlist_ref(resume_position-1,&ref) &&
            !playback_select_ref(&ref,state,resume_position,playlist_count())) {
            *(volatile u32 *)0x0300d1cc=resume_ms;
            *(volatile u8 *)0x0300d1d0=1;
            return 0;
        }
        *(volatile u32 *)0x0300d1cc=0;
        *(volatile u8 *)0x0300d1d0=0;
        return playback_playlist_step(state,0);
    }
    u32 pos=((u16 *)state)[1]; struct media_ref ref;
    if (pos && playlist_ref(pos-1,&ref) && !playback_select_ref(&ref,state,pos,playlist_count())) return 0;
    return playback_playlist_step(state,0);
}
int playback_advance(u8 *state,int steps)
{
    if (!playback_active) return FW(0x03060c10,int,u8 *,int)(state,steps);
    if (steps>512 || steps < -512) return 19;
    int direction=steps<0?-1:1;
    u32 n=steps<0?(u32)-steps:(u32)steps;
    for (u32 i=0;i<n;i++) {
        int result=playback_playlist_move(state,direction,SERVICE[2]==1);
        if (result) return result;
    }
    return 0;
}
