#include "feedback.h"
#include "session.h"

struct window {
    struct window *child,*parent;
    u32 (*service)(void),(*key)(void);
    void (*paint)(void),(*init)(const void *),(*uninit)(void);
};
#define MUSIC ((struct window *)0x0300e6bc)
#define TICKS (*(volatile u32 *)0x0300d144)
#define post FW(0x0306b040,void,u32)
#define destroy FW(0x03059840,u32,struct window *)
/* Low two bits are the mailbox result; upper bits identify the book session.
 * One atomic word prevents a late write or UI claim resurrecting old feedback. */
static u32 mailbox;
static u32 shown,shown_token,since;
static struct window popup;
static const u16 saved[]={'B','o','o','k','m','a','r','k',' ','s','a','v','e','d',0};
static const u16 failed[]={'B','o','o','k','m','a','r','k',' ','f','a','i','l','e','d',0};
u32 feedback_token(void) { return __atomic_load_n(&mailbox,__ATOMIC_ACQUIRE)&~3u; }
void feedback_result(u32 token,int success)
{
    u32 old=__atomic_load_n(&mailbox,__ATOMIC_ACQUIRE);
    while((old&~3u)==token) {
        u32 next=token|(success?1u:2u);
        if(__atomic_compare_exchange_n(&mailbox,&old,next,0,__ATOMIC_RELEASE,__ATOMIC_RELAXED))return;
    }
}
void feedback_cancel(void)
{
    u32 old=__atomic_load_n(&mailbox,__ATOMIC_RELAXED);
    while(!__atomic_compare_exchange_n(&mailbox,&old,(old+4)&~3u,0,__ATOMIC_RELEASE,__ATOMIC_RELAXED)){}
}
static void uninit(void) { shown=0; }
static void init(const void *arg) { (void)arg;since=TICKS; }
static u32 key(void) { return 0; }
static u32 service(void)
{
    if(!playback_active || feedback_token()!=shown_token || (u32)(TICKS-since)>=150) {
        destroy(&popup);
        post(57); /* native player full redraw; 227 means native error recovery */
    }
    return 0;
}
static void paint(void)
{
    if(!shown || !playback_active || feedback_token()!=shown_token)return;
    u32 old_a=FW(0x03067904,u32,u32)(0);
    u32 old_b=FW(0x030678e0,u32,u32)(1);
    __builtin_memset((void *)0x03007d88,0,640);
    /* Renderer mutates the rectangle, so allocate it afresh each draw. */
    u16 rect[4]={0,8,127,23};
    FW(0x03052b08,void,u16 *,const u16 *,u32,u32,void *)(rect,shown==1?saved:failed,2,1,0);
    FW(0x030643d8,void,u32,u32,u32,u32)(0,0,128,31);
    /* The setter maps logical0/2 to raw2/0 but returns the old RAW value.
     * Restore the raw field directly; passing it back would invert the mode. */
    *(volatile u16 *)0x0300d6e0=(u16)old_a;
    FW(0x030678e0,u32,u32)(old_b);
}
void feedback_poll(u32 transition)
{
    if(transition || !playback_active)return;
    /* Callback identity proves the parent is module27's MusicWin, rather than
     * another overlay's data at the same address. */
    if((u32)MUSIC->service!=0x0307a4df || (u32)MUSIC->paint!=0x0307b993)return;
    if(MUSIC->child)return;
    u32 old=__atomic_load_n(&mailbox,__ATOMIC_ACQUIRE);
    if(!(old&3))return;
    if(!__atomic_compare_exchange_n(&mailbox,&old,old&~3u,0,__ATOMIC_ACQ_REL,__ATOMIC_RELAXED))return;
    shown=old&3;shown_token=old&~3u;
    popup=(struct window){0,0,service,key,paint,init,uninit};
    FW(0x03059828,u32,struct window *,struct window *,const void *)(MUSIC,&popup,0);
}
