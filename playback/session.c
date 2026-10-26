#include "session.h"
#include "bookmarks.h"
#include "feedback.h"
#include "queue.h"
#include "resume.h"
#include "last_book.h"
#include "speed.h"
#include "book_preview.h"
#include "navigation.h"
#define STATE ((u8 *)0x0300d85c)
#define SERVICE ((u32 *)0x03039708)
#define PLAYER ((u32 *)0x03023090)
/* Book menu retains this path through launch failure; publish only validated paths. */
u16 playback_launch_buffer[256];
#define pending_path playback_launch_buffer
static u8 pending, path_armed, starting, meditation_pending;
static u32 resume_position, resume_ms;
static u8 override_armed, override_pending, starting_explicit, override_rate;
void playback_launch_rate(u32 quarters) { override_rate=quarters; }
static u32 override_chapter, override_ms, override_signature;
static volatile u32 bookmark_pending;
static volatile u32 bookmark_session;
static u32 bookmark_chapter, bookmark_ms, bookmark_token, bookmark_feedback_token;
static struct {
    u16 path[256];
    struct media_ref ref;
    u32 signature, generation;
    u8 valid, device, filesystem;
} current;
u16 *playback_book_path(void) { return current.path; }
static u32 rate_generation;
static u16 rate_polls, rate_position;
static u8 rate_quarters, rate_paused, rate_previous, rate_previous_actual;
static int rate_status;
static u32 jump_mark,jump_entry[2];
u32 playback_active;
static __attribute__((noipa)) int rate_fail(void)
{
    if(rate_status==2){
        playback_speed_set(rate_previous_actual);playback_speed_launch();
        playback_speed_set(rate_previous);
    }
    return rate_status=-1;
}
static u16 half(const u8 *p) { return p[0] | (u16)p[1]<<8; }
static u32 word(const u8 *p) { return half(p) | (u32)half(p+2)<<16; }
static void player_stop(void)
{
    /* Match the native browser handoff, not Now Playing's reuse-existing-
     * service route. Removing this callback synchronously stops the decoder
     * and reaches book_save while the book context is still intact. */
    *(volatile u8 *)0x0300d1d0=0;
    *(volatile u32 *)0x0300d1cc=0;
    FW(0x03059910,void,void *,void *)((void *)0x0300dc1c,(void *)0x0302315c);
    *(volatile u8 *)0x0300d1d0=0;
}
static void player_open(void)
{
    FW(0x0306b082,void,u32)(396);
    FW(0x0306b040,void,u32)(349);
    FW(0x0306b082,void,u32)(395);
    const u16 argument=1;
    FW(0x0306b26a,void,u32,const void *)(3,&argument);
}
static void player_relaunch(void) { player_stop();player_open(); }
/* No browser pointer survives this synchronous stop/save/copy transaction. */
int playback_folder_launch(const struct playlist_queue *queue,u32 position)
{
    struct media_ref ref;u8 checked[96];
    if(rate_status==1 || rate_status==2 || !queue || !queue->count ||
       queue->count>PLAYLIST_CAPACITY || !position || position>queue->count ||
       !playlist_queue_ref(queue,position-1,&ref) ||
       playback_select_ref(&ref,checked,position,queue->count))return 0;
    player_stop(); /* old queue and book context remain intact through save */
    book_clear();current.valid=0;current.generation++;
    current.device=*(const u8 *)0x0300d173;current.filesystem=FS_TYPE;
    playlist_import(queue);
    path_armed=override_armed=override_pending=override_rate=0;
    resume_position=position;resume_ms=0;starting_explicit=1;
    playback_active=2;pending=2;starting=1;
    *(u16 *)(STATE+0xf2)=99;
    player_open();return 1;
}
static int folder_changed(void)
{
    return playback_active==2 && (current.device!=*(const u8 *)0x0300d173 || current.filesystem!=FS_TYPE);
}
static int m3u_name(const u8 *node)
{
    u32 n=0;
    while (n<256 && half(node+0x70+n*2)) n++;
    return n>=5 && n<256 && half(node+0x70+(n-4)*2)=='.' &&
           (half(node+0x70+(n-3)*2)|32)=='m' &&
           half(node+0x70+(n-2)*2)=='3' &&
           (half(node+0x70+(n-1)*2)|32)=='u';
}
static const u8 *selected_node(void)
{
    const u8 *browser=(const u8 *)0x03005f6c;
    u32 selected=half(browser+0x1ee), address=word(browser);
    if (selected>1) return 0;
    for (u32 i=0;i<=selected;i++) {
        if (address!=0x0300e73c && address!=0x0300e9ac) return 0;
        if (i<selected) address=word((const u8 *)address+4);
    }
    return (const u8 *)address;
}
const u8 *playback_browser_selected_node(void) { return selected_node(); }
const u8 *playback_browser_selected_m3u(void)
{
    const u8 *node=selected_node();
    return node && half((const u8 *)0x0300ec1c+8)==3 && m3u_name(node)?node:0;
}
/* Return selected node; low bit marks a captured playlist launch. No queue is
 * replaced while browsing folders. Copy the resident audio whitelist (the old local copy is now a loader). */
u32 playback_browser_select(u8 *extensions)
{
    if(rate_status==2)return 0;
    u32 requested=override_armed;override_armed=0;
    __builtin_memcpy(extensions,(const void *)0x03005ab4,43);
    extensions[43]=0;
    if (path_armed) {
        path_armed=0;pending=1;override_pending=requested;meditation_pending=0;
        return 1; /* Existing launch bridge does not dereference this sentinel. */
    }
    const u8 *node=selected_node();if(!node)return 0;
    u32 address=(u32)node;
    if(playback_browser_selected_m3u()==node){
        pending=0;
        if (playback_scratch_busy) return 0;
        playback_scratch_busy=1;
        u16 *candidate=(u16 *)playback_scratch;
        int valid=playback_browser_path(node,candidate);
        u32 n=0;
        if(valid && requested){
            while(candidate[n] && candidate[n]==pending_path[n])n++;
            valid=candidate[n]==pending_path[n];
        }
        if(valid)__builtin_memcpy(pending_path,candidate,sizeof pending_path);
        playback_scratch_busy=0;
        if(!valid)return 0;

        pending=1;override_pending=requested;meditation_pending=navigation_content_kind()<0;
        return address|1;
    }
    if (node[0x4e]) pending=override_rate=0; /* a deliberate ordinary-file selection */
    return address;
}
void playback_launch_override(u32 chapter,u32 milliseconds,u32 signature)
{
    override_chapter=chapter;override_ms=milliseconds;override_signature=signature;
    override_armed=1;
}
int playback_launch_path(const u16 *path,u32 chapter,u32 milliseconds,u32 signature)
{
    if(rate_status==2)return 0;
    path_armed=override_armed=0;
    if (!path || path[0]!='/') return 0;
    u32 n=0;while(n<256 && path[n])n++;
    if (n<2 || n>=256 || path[n-1]=='/') return 0;
    if(path!=pending_path)__builtin_memcpy(pending_path,path,(n+1)*2);
    playback_launch_override(chapter,milliseconds,signature);path_armed=1;
    return 1;
}
void playback_launch_cancel(void) { override_armed=path_armed=override_rate=0; }
void playback_begin(const u16 *argument)
{
    /* Null means reopening current context; non-null launches a selection. */
    if (!pending && (argument || half(STATE+0xf2)!=99)) { playback_active=0; book_clear(); }
}
int playback_prepare(u32 mode)
{
    if (pending==2) { pending=0;return folder_changed(); }
    if (pending) {
        struct m3u_stats stats;
        u32 meditation=meditation_pending;meditation_pending=0;
        pending=0; playback_active=0;book_clear();
        int count=playback_load_playlist(pending_path,&stats);
        u32 explicit=override_pending;override_pending=0;starting_explicit=0;
        if (count<=0 || (explicit && (playlist_signature()!=override_signature || override_chapter>(u32)count))) {
            override_rate=0;
            if(rate_status==2)rate_fail();
            FW(0x0306b040,void,u32)(245);
            return 1;
        }
        if(meditation){
            current.valid=0;current.generation++;
            current.device=*(const u8 *)0x0300d173;current.filesystem=FS_TYPE;
            override_rate=0;resume_position=1;resume_ms=0;
            playback_active=2;starting=1;return 0;
        }
        resume_position=book_load(pending_path,&resume_ms);
        if(explicit && override_chapter){resume_position=override_chapter;resume_ms=override_ms;starting_explicit=1;}
        bookmarks_open(pending_path,playlist_signature());
        current.valid=0;current.generation++;
        if(playback_lookup(pending_path,&current.ref)==1 && !(current.ref.attrs&16)){
            __builtin_memcpy(current.path,pending_path,sizeof current.path);
            current.signature=playlist_signature();current.device=*(const u8 *)0x0300d173;
            current.filesystem=FS_TYPE;current.valid=1;
        }
        if(override_rate)playback_speed_set(override_rate);
        override_rate=0;
        if(rate_status==2)playback_speed_set(rate_quarters);
        playback_speed_launch();
        if(rate_status==2 && jump_mark)playback_speed_set(rate_previous);
        playback_active=1; starting=1;
        if(explicit && rate_status!=2)last_book_remember(pending_path);
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
    if(folder_changed())return 19;
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
            if(rate_status==2){
                *(volatile u16 *)0x0300d81a=rate_paused?3:0;
                if(rate_paused)*(volatile u16 *)0x0300d7f0=4;
                rate_status=3;
            }
            *(volatile u32 *)0x0300d1cc=resume_ms;
            *(volatile u8 *)0x0300d1d0=1;
            return 0;
        }
        *(volatile u32 *)0x0300d1cc=0;
        *(volatile u8 *)0x0300d1d0=0;
        if(starting_explicit){if(rate_status==2)rate_fail();return 19;}
        return playback_playlist_step(state,0);
    }
    u32 pos=((u16 *)state)[1]; struct media_ref ref;
    if (pos && playlist_ref(pos-1,&ref) && !playback_select_ref(&ref,state,pos,playlist_count())) return 0;
    return playback_playlist_step(state,0);
}
int playback_advance(u8 *state,int steps)
{
    if (!playback_active) return FW(0x03060c10,int,u8 *,int)(state,steps);
    if(folder_changed())return 19;
    if (steps>512 || steps < -512) return 19;
    int direction=steps<0?-1:1;
    u32 n=steps<0?(u32)-steps:(u32)steps;
    for (u32 i=0;i<n;i++) {
        int result=playback_playlist_move(state,direction,SERVICE[2]==1);
        if (result) return result;
    }
    return 0;
}

/* Capture only a queue position whose raw decoder identity still matches.
 * Shared by manual bookmarks and automatic resume; called on player service. */
u32 playback_position(struct media_ref *chapter,u32 *milliseconds)
{
    if (playback_active!=1 || playback_scratch_busy) return 0;
    u32 position=half(STATE+2);
    if (!position || !playlist_ref(position-1,chapter)) return 0;
    const u8 *raw=STATE+0x14;
    u32 cluster=(u32)half(raw+20)<<16|half(raw+26);
    if (cluster!=chapter->cluster) return 0;
    const u32 *info=*(const u32 *volatile *)0x03039714;
    if ((u32)info!=0x03023090) return 0;
    u32 time=info[1];
    playback_speed_position(&time);
    *milliseconds=time>info[0]?info[0]:time;
    return position;
}
int playback_add_bookmark(void)
{
    struct media_ref chapter;u32 ms;
    u32 position=playback_position(&chapter,&ms);
    return position?bookmarks_change(~0u,position,ms):-1;
}
void playback_cancel_bookmark(void) { bookmark_session++;bookmark_pending=0;feedback_cancel(); }
int playback_request_bookmark(void)
{
    struct media_ref chapter;u32 ms;
    if (bookmark_pending) return -1;
    u32 token=bookmark_session;
    u32 position=playback_position(&chapter,&ms);
    if (!position) { feedback_result(feedback_token(),0);return -1; }
    bookmark_chapter=position;bookmark_ms=ms;bookmark_token=token;
    bookmark_feedback_token=feedback_token();
    __asm__ volatile ("" ::: "memory");
    bookmark_pending=1;
    return 0;
}
u32 playback_bookmark_poll(u32 message)
{
    if(playback_active==1 && current.valid && rate_status!=1 && rate_status!=2 &&
       !playback_scratch_busy && *(volatile u16 *)0x0300d81a==0)book_autosave();
    if (bookmark_pending && !playback_scratch_busy) {
        __asm__ volatile ("" ::: "memory");
        u32 position=bookmark_chapter,ms=bookmark_ms,token=bookmark_token,notice=bookmark_feedback_token;
        bookmark_pending=0;
        if (playback_active==1 && token==bookmark_session)
            feedback_result(notice,bookmarks_change(~0u,position,ms)>=0);
    }
    return FW(0x0306b05c,u32,u32)(message);
}

void playback_rate_cancel(void)
{
    if(rate_status==1)rate_status=-1;
}
static int same_ref(const struct media_ref *a,const struct media_ref *b)
{
    return a->parent.cluster==b->parent.cluster && a->index==b->index &&
        a->cluster==b->cluster && a->size==b->size;
}
/* Revalidate physical chapter identity as well as playlist bytes: replacing an
 * MP3 without editing its M3U must not inherit the old chapter's source time. */
static __attribute__((noipa)) u32 rate_preflight(u32 *ms)
{
    struct media_ref checked,chapter;u8 selected[96];
    u32 generation=current.generation,position=playback_position(&chapter,ms);
    if(!current.valid || !position || current.device!=*(const u8 *)0x0300d173 ||
       current.filesystem!=FS_TYPE || playback_lookup(current.path,&checked)!=1 ||
       !same_ref(&checked,&current.ref) || (checked.attrs&16) ||
       book_preview_open(current.path)<=0 || book_preview_signature()!=current.signature ||
       !book_preview_ref(position-1,&checked) || !same_ref(&checked,&chapter) ||
       playback_select_ref(&chapter,selected,position,playlist_count()) ||
       word(selected+0x30)!=word(STATE+0x30) ||
       generation!=current.generation || !playback_active ||
       position!=playback_position(&chapter,ms))return 0;
    return position;
}
int playback_bookmarks_open(void)
{
    u32 ms;
    return rate_status!=1 && rate_status!=2 && rate_preflight(&ms)!=0;
}
static int jump_valid(void)
{
    struct media_ref a,b;u8 selected[96];u32 entry[2];
    return book_preview_mark(jump_mark-1,entry) && entry[0]==jump_entry[0] && entry[1]==jump_entry[1] &&
        entry[0] && playlist_ref(entry[0]-1,&a) && book_preview_ref(entry[0]-1,&b) && same_ref(&a,&b) &&
        !playback_select_ref(&a,selected,entry[0],playlist_count());
}
static int restart_request(u32 quarters,u32 mark)
{
    if(rate_status==1 || rate_status==2)return -1;
    jump_mark=mark;
    if(mark && !book_preview_mark(mark-1,jump_entry))return rate_status=-1;
    u32 ms,position=rate_preflight(&ms);
    if(!position || (mark && !jump_valid()))return rate_status=-1;
    u32 state=*(volatile u16 *)0x0300d81a;
    if(state!=0 && state!=3)return rate_status=-1;
    rate_paused=state==3;rate_generation=current.generation;rate_quarters=quarters;rate_polls=0;
    rate_position=position;rate_previous=playback_speed_get();
    rate_previous_actual=playback_speed_launched();rate_status=1;
    if(!rate_paused)FW(0x030816ee,void,void)();
    return playback_rate_poll();
}
int playback_rate_request(u32 quarters)
{
    if(rate_status==1 || rate_status==2)return -1;
    if(quarters<4 || quarters>8 || !playback_speed_supported())return rate_status=-1;
    if(quarters==playback_speed_actual()){playback_speed_set(quarters);return rate_status=3;}
    return restart_request(quarters,0);
}
int playback_bookmark_jump(u32 index)
{ return index<60?restart_request(playback_speed_launched(),index+1):-1; }
int playback_seek_request(int direction)
{
    struct media_ref chapter;u32 ms;
    if(rate_status==1 || rate_status==2)return -1;
    u32 position=playback_position(&chapter,&ms),state=*(volatile u16 *)0x0300d81a;
    if(!position || !current.valid || current.device!=*(const u8 *)0x0300d173 ||
       current.filesystem!=FS_TYPE || (state!=0 && state!=3))return -1;
    u32 end=PLAYER[0]>1000?PLAYER[0]-1000:0;
    u32 target=direction<0?(ms>10000?ms-10000:0):(ms>end || end-ms<10000?end:ms+10000);
    if(target>end)target=end;
    jump_mark=~0u;jump_entry[0]=target;
    rate_position=position;rate_paused=state==3;rate_generation=current.generation;rate_polls=0;rate_status=1;
    if(!rate_paused)FW(0x030816ee,void,void)();
    return playback_rate_poll();
}
int playback_rate_poll(void)
{
    if(rate_status!=1)return rate_status;
    if(!playback_active || current.generation!=rate_generation ||
       *(volatile u16 *)0x0300d81a!=3 || ++rate_polls>200)return rate_status=-1;
    if(!playback_speed_drained())return 1;
    if(jump_mark==~0u){
        struct media_ref chapter;u32 ms;
        if(current.device!=*(const u8 *)0x0300d173 || current.filesystem!=FS_TYPE ||
           playback_position(&chapter,&ms)!=rate_position)return rate_status=-1;
        FW(0x03082524,void,u32,u32)(251,jump_entry[0]);
        /* Native command 251 seeks the decoder but does not update this clock. */
        PLAYER[1]=jump_entry[0];
        if(!rate_paused)FW(0x03081f10,void,void)();
        FW(0x0306b040,void,u32)(57);return rate_status=3;
    }
    u32 ms,position=rate_preflight(&ms);
    if(!position || position!=rate_position || (jump_mark && !jump_valid()))return rate_status=-1;
    if(jump_mark){position=jump_entry[0];ms=jump_entry[1];}
    if(!playback_launch_path(current.path,position,ms,current.signature))return rate_status=-1;
    /* Resident player handoff, independent of the browser overlay. */
    path_armed=override_armed=0;pending=override_pending=1;rate_status=2;
    player_relaunch();return rate_status;
}
