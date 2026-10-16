#include "session.h"
#include "speed.h"
#include "book_menu.h"
#include "book_preview.h"
#define MARKS 0xff10u
#define PAGE 0xff12u
#define ENTRY 0xff20u
#define MENU 0xff00u
void player_speed_menu_record(u32 id,u16 *out)
{
    if(id<MENU) {
        FW(0x03067988,void,u32,u16 *)(id,out);
        if(id==237) {
            if(playback_speed_supported())out[8+out[7]++]=MENU;
            if(playback_active==1)out[8+out[7]++]=MARKS;
        }
        return;
    }
    for(u32 i=0;i<29;i++)out[i]=0xffff;
    if(id>=MARKS) {
        u32 n=book_preview_marks(),start=0,count=0;
        out[0]=id;out[1]=MARKS;out[2]=0;out[7]=0;
        if(id==MARKS){
            out[1]=237;out[2]=playback_speed_supported()?7:6;
            out[3]=MARKS+1;out[8]=MARKS+1;out[7]=1;
            if(n>20){for(u32 i=0;i<(n>40?3u:2u);i++)out[8+out[7]++]=PAGE+i;return;}
            count=n;
        }else if(id>=PAGE && id<PAGE+3){
            start=(id-PAGE)*20;out[3]=ENTRY+start;out[2]=1+id-PAGE;
            count=n>start?n-start:0;if(count>20)count=20;
        }else{out[2]=id==MARKS+1?0:1+id-ENTRY;return;}
        for(u32 i=0;i<count;i++)out[8+out[7]++]=ENTRY+start+i;
        return;
    }
    out[0]=id;out[1]=id==MENU?237:MENU;out[2]=id==MENU?6:id-MENU-1;
    out[7]=0;
    if(id==MENU && playback_speed_supported()) {
        out[3]=MENU+1;out[7]=5;
        for(u32 i=0;i<5;i++)out[8+i]=MENU+1+i;
    }
}
void player_speed_menu_text(u32 id,u16 *out,u32 count)
{
    if(id<MENU){FW(0x03067860,void,u32,u16 *,u32)(id,out,count);return;}
    count/=2;
    const char *s="";
    if(id>=ENTRY && id<ENTRY+60){
        u16 label[32];book_mark_label(label,id-ENTRY);
        u32 i=0;while(i+1<count && label[i]){out[i]=label[i];i++;}if(count)out[i]=0;return;
    }
    if(id==MARKS)s="Bookmarks";
    if(id==MARKS+1)s="Add bookmark";
    if(id>=PAGE && id<PAGE+3){static const char *const pages[]={"1-20","21-40","41-60"};s=pages[id-PAGE];}
    if(id==MENU)s="Speed";
    if(id>MENU && id<=MENU+5)s=playback_speed_label_text(id-MENU+3);
    while(count && *s){*out++=*s++;count--;}
    if(count)*out=0;
}
u32 player_speed_menu_action(u32 id)
{
    if(id==MARKS){if(!playback_bookmarks_open())return 0;}
    if(id<=MENU || id==MARKS || (id>=PAGE && id<PAGE+3))return FW(0x03079fbc,u32,u32)(id);
    if(id==MARKS+1){
        if(playback_active!=1)return 0;
        playback_request_bookmark();FW(0x0306b26a,void,u32,void *)(3,0);return 1;
    }
    int result;
    if(id>=ENTRY && id<ENTRY+60)result=playback_bookmark_jump(id-ENTRY);
    else if(id<=MENU+5)result=playback_rate_request(id-MENU+3);
    else return 0;
    if(result<0 || result==1)return 0;
    if(result!=2)FW(0x0306b26a,void,u32,void *)(3,0);
    return 1;
}

u32 player_speed_menu_service(void)
{
    if(playback_rate_poll()==2)return 1;
    u32 result=FW(0x03079a74,u32,void)();
    if(result)playback_rate_cancel();
    return result;
}
