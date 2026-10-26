#include "session.h"
#include "last_book.h"
static u16 title[64]; /* Native marquee retains the source pointer. */
extern void playback_speed_label(void);
u32 playback_book_screen(void)
{
    if(playback_active==1 && !*(const u8 *)0x0300e6e3){
        u32 mode=FW(0x03067904,u32,u32)(0);
        for(u32 row=0;row<2;row++){
            const u16 *text=(const u16 *)0x03039928;
            if(!row){book_path_title(playback_book_path(),title,64);text=title;}
            else if(!*text)text=(const u16 *)0x03039798;
            void *marquee=(void *)(row?0x03005f0c:0x03005edc);
            /* Native painters consume dirty events and replace this pointer
             * on a full redraw. Reclaim the row after that replacement. */
            if(*(const u16 **)((u8 *)marquee+12)==text)continue;
            u16 rect[4]={row?0:12,row?12:0,row?86:127,row?23:11};
            if(row)for(u32 x=0;x<86;x++){
                u8 *p=(u8 *)0x03007d88+x*5;p[1]&=15;p[2]=0;
            }
            FW(0x03052b08,void,u16 *,const u16 *,u32,u32,void *)(rect,text,0,1,marquee);
            FW(0x03052fe4,void,void *)(marquee);
        }
        *(volatile u16 *)0x0300d6e0=mode;
        static const u16 book[]={0x0,0x1fe,0x102,0x102,0x204,0x3f8,0x204,0x102,0x102,0x1fe,0x0,0x0};
        for(u32 x=0;x<128;x++){
            u8 *p=(u8 *)0x03007d88+x*5;
            if(x<12){p[0]=book[x];p[1]=(p[1]&0xf0)|(book[x]>>8);}
            if(x>=87 && x<115)p[3]=0; /* mode and favorite; battery starts at115 */
        }
        playback_speed_label();
    }
    return FW(0x03051574,u32,u32)(6);
}
