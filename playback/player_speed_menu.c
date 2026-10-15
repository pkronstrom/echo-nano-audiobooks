#include "session.h"
#include "speed.h"
#include "book_menu.h"
#define MENU 0xff00u
void player_speed_menu_record(u32 id,u16 *out)
{
    if(id<MENU) {
        FW(0x03067988,void,u32,u16 *)(id,out);
        if(id==237 && playback_speed_supported()) {
            out[7]=7;out[14]=MENU;
        }
        return;
    }
    for(u32 i=0;i<29;i++)out[i]=0xffff;
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
    if(id==MENU)s="Speed";
    if(id>MENU && id<=MENU+5)s=playback_speed_label_text(id-MENU+3);
    while(count && *s){*out++=*s++;count--;}
    if(count)*out=0;
}
u32 player_speed_menu_action(u32 id)
{
    if(id<=MENU)return FW(0x03079fbc,u32,u32)(id);
    if(id>MENU+5)return 0;
    int result=playback_rate_request(id-MENU+3);
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
