#include "book_menu.h"
#include "book_preview.h"
#include "session.h"
#include "last_book.h"
#include "speed.h"
#define B ((u8 *)0x03005f6c)
#define C ((u8 *)0x0300ec1c)
#define H(p) (*(u16 *)(p))
#define W(p) (*(u32 *)(p))
#define post FW(0x0306b040,void,u32)
/* Native browser has exactly two resident nodes. Save real identities before
 * substituting labels; synthetic nodes must never reach native file actions. */
static u32 browser_saved[128],control_saved[8],nodes_saved[312];
static u16 path[256];
static u32 active,returning,view,choice,selected_mark,direct_folder,path_launch;
enum { TOP, CHAPTERS, MARKS, MARK_ACTION, DELETE_CONFIRM, ERROR_VIEW, BOOK_ERROR, SPEED };
static u8 *node(u32 slot) { return (u8 *)(slot?0x0300e9ac:0x0300e73c); }
static void restore(void)
{
    __builtin_memcpy(B,browser_saved,sizeof browser_saved);
    __builtin_memcpy(C,control_saved,sizeof control_saved);
    __builtin_memcpy(node(0),nodes_saved,sizeof nodes_saved);
}
/* Saved browser records contain physical identities, not durable paths. A
 * same-name replacement must never resurrect the old native cursor. */
static int parent_valid(void)
{
    if(!direct_folder)return 1;
    const u8 *browser=(const u8 *)browser_saved;
    u32 address=W(browser),selected=H(browser+0x1ee);
    if(selected>1)return 0;
    const u8 *entry=0;
    for(u32 i=0;i<=selected;i++){
        if(address!=0x0300e73c && address!=0x0300e9ac)return 0;
        entry=(const u8 *)nodes_saved+(address-0x0300e73c);
        address=W(entry+4);
    }
    u16 current[256];
    if(!playback_browser_directory_at(browser,entry,current))return 0;
    u32 i=0;while(current[i]){if(current[i]!=path[i])return 0;i++;}
    return path[i]=='/';
}
static u32 leave(void)
{
    active=0;
    if(parent_valid()){restore();post(333);post(335);return 1;}
    FW(0x0306b26a,void,u32,const void *)(0,0);return 2;
}
static u32 items(void)
{
    if(view==TOP)return 4;
    if(view==SPEED)return 5;
    if(view==CHAPTERS)return book_preview_count();
    if(view==MARKS){u32 n=book_preview_marks();return n?n:1;}
    return 2;
}
static u16 *text(u16 *out,const char *value)
{ while(*value)*out++=(u8)*value++;*out=0;return out; }
static u16 *number(u16 *out,u32 n)
{
    char digits[10];u32 count=0;
    do{digits[count++]=(char)('0'+n%10);n/=10;}while(n);
    while(count)*out++=digits[--count];
    *out=0;return out;
}
static u16 *time_text(u16 *out,u32 ms)
{
    u32 seconds=ms/1000,hours=seconds/3600,minutes=seconds/60%60;
    if(hours<10)*out++='0';
    out=number(out,hours);*out++=':';
    *out++='0'+minutes/10;*out++='0'+minutes%10;*out++=':';
    *out++='0'+seconds%60/10;*out++='0'+seconds%10;*out=0;return out;
}
const char *playback_speed_label_text(u32 quarters)
{
    static const char *const names[]={"1x","1.25x","1.5x","1.75x","2x"};
    return names[quarters>=4 && quarters<=8?quarters-4:0];
}
static void label(u16 *out,u32 index)
{
    if(view==TOP){
        if(index==1){text(out,"Chapters");return;}
        if(index==2){text(out,"Bookmarks");return;}
        if(index==3){text(text(out,"MP3 speed "),playback_speed_label_text(playback_speed_get()));return;}
        u32 ms,chapter=book_preview_resume(&ms);
        out=text(out,"Continue ");out=number(out,chapter?chapter:1);
        out=text(out," ");time_text(out,ms);return;
    }
    if(view==SPEED){text(out,playback_speed_label_text(index+4));return;}
    if(view==CHAPTERS){out=text(out,"Chapter ");number(out,index+1);return;}
    if(view==MARKS){
        u32 entry[2];
        if(!book_preview_mark(index,entry)){text(out,"No bookmarks");return;}
        out=text(out,"Ch ");out=number(out,entry[0]);out=text(out," ");time_text(out,entry[1]);return;
    }
    if(view==MARK_ACTION){text(out,index?"Delete bookmark":"Play bookmark");return;}
    if(view==DELETE_CONFIRM){text(out,index?"Cancel":"Delete bookmark?");return;}
    text(out,index?"Back":view==BOOK_ERROR?"Book unavailable":"Delete failed");
}
static void draw(void)
{
    u32 count=items();if(!count)count=1;if(choice>=count)choice=count-1;
    u32 page=choice&~1u;
    H(B+0x1cc)=0;H(B+12)=H(B+16)=count;H(B+14)=0;
    H(B+0x1ce)=page;H(B+0x1ee)=H(B+0x1f0)=choice&1;
    H(B+8)=count-page>1?2:1;H(C+12)=0;
    /* Use stable native node addresses, independent of original list head. */
    W(B)=(u32)node(0);W(node(0)+4)=(u32)node(1);W(node(1)+4)=(u32)node(0);
    for(u32 slot=0;slot<2;slot++){
        u8 *entry=node(slot);__builtin_memset(entry+8,0,616);
        if(page+slot<count)label((u16 *)(entry+0x70),page+slot);
    }
    post(333);post(335);
}
void book_menu_reset(void) { active=returning=0; }
int book_menu_open_selected(void)
{
    if(active||returning)return 0;
    const u8 *selected=playback_browser_selected_m3u();
    direct_folder=0;
    if(selected){if(!playback_browser_path(selected,path))return 1;}
    else{
        selected=playback_browser_selected_node();
        if(!selected || H(C+8)!=3 || selected[0x4e] ||
           !playback_browser_directory(selected,path))return 0;
        u32 length=0;while(path[length])length++;
        if(length+9>=256)return 0;
        const char *suffix="/BOOK.M3U";
        for(u32 i=0;i<=9;i++)path[length+i]=(u8)suffix[i];
        struct media_ref ref;
        if(playback_lookup(path,&ref)!=1 || (ref.attrs&16))return 0;
        direct_folder=1;
    }
    __builtin_memcpy(browser_saved,B,sizeof browser_saved);
    __builtin_memcpy(control_saved,C,sizeof control_saved);
    __builtin_memcpy(nodes_saved,node(0),sizeof nodes_saved);
    path_launch=direct_folder;
    int available=book_preview_open(path)>0;
    active=1;view=available?TOP:BOOK_ERROR;choice=available?0:1;draw();return 1;
}
static int launch(u32 chapter,u32 ms)
{
    u32 signature=book_preview_signature();
    restore();active=0;returning=1;
    if(path_launch){
        if(!playback_launch_path(path,chapter,ms,signature)){
            returning=0;active=1;view=BOOK_ERROR;choice=1;draw();return 0;
        }
    }else playback_launch_override(chapter,ms,signature);
    if(!FW(0x0307acb6,int,void)()){
        playback_launch_cancel();returning=0;active=1;view=TOP;choice=0;draw();return 0;
    }
    return 1;
}
int book_menu_continue_last(void)
{
    u32 signature;
    if(active || returning || !last_book_snapshot(path,&signature))return 0;
    if(book_preview_open(path)<=0 || book_preview_signature()!=signature)return 0;
    __builtin_memcpy(browser_saved,B,sizeof browser_saved);
    __builtin_memcpy(control_saved,C,sizeof control_saved);
    __builtin_memcpy(nodes_saved,node(0),sizeof nodes_saved);
    direct_folder=0;path_launch=1;active=1;view=TOP;choice=0;
    return launch(0,0)?2:1;
}
int book_menu_browser_init(void)
{
    if(!returning){active=0;return 0;}
    returning=0;
    /* A failed re-open can mean replaced/removed media. Keep the native
     * freshly initialized browser, never resurrect old entry identities. */
    if(!parent_valid() || book_preview_open(path)<=0){active=0;return 0;}
    restore();
    active=1;view=TOP;choice=0;draw();return 1;
}
u32 book_menu_event(u32 message)
{
    if(!active)return 0;
    if(message==0x20000040||message==0x40001000){
        if(view==BOOK_ERROR){if(direct_folder)return leave();active=0;FW(0x0306b26a,void,u32,const void *)(0,0);return 2;}
        if(view==TOP)return leave();
        if(view==DELETE_CONFIRM){view=MARK_ACTION;choice=0;}
        else if(view==MARK_ACTION||view==ERROR_VIEW){view=MARKS;choice=selected_mark;}
        else{choice=view==CHAPTERS?1:view==SPEED?3:2;view=TOP;}
        draw();return 1;
    }
    if(message==0x40000004||message==0x30000004){choice=(choice+1)%items();draw();return 1;}
    if(message==0x40000008||message==0x30000008){choice=choice?choice-1:items()-1;draw();return 1;}
    if(message==0x40000040){
        if(view==BOOK_ERROR){if(direct_folder)return leave();active=0;FW(0x0306b26a,void,u32,const void *)(0,0);return 2;}
        if(view==TOP){
            if(!choice)return launch(0,0)?2:1;
            view=choice==1?CHAPTERS:choice==2?MARKS:SPEED;
            choice=view==SPEED?playback_speed_get()-4:0;
        }else if(view==SPEED){
            /* Desired rate is latched only by the next playback launch. */
            playback_speed_set(choice+4);view=TOP;choice=3;
        }else if(view==CHAPTERS)return launch(choice+1,0)?2:1;
        else if(view==MARKS){if(book_preview_marks()){selected_mark=choice;view=MARK_ACTION;choice=0;}}
        else if(view==MARK_ACTION){
            if(!choice){u32 entry[2];if(book_preview_mark(selected_mark,entry))return launch(entry[0],entry[1])?2:1;}
            else{view=DELETE_CONFIRM;choice=1;} /* safe default: Cancel */
        }else if(view==DELETE_CONFIRM){
            if(choice){view=MARK_ACTION;choice=0;}
            else if(book_preview_delete(selected_mark)>0){view=MARKS;choice=selected_mark;}
            else{view=ERROR_VIEW;choice=1;}
        }else{view=MARKS;choice=selected_mark;}
        draw();return 1;
    }
    return message==0x20000080||message==0x40000002||message==0x40010000||message==0x50010000;
}
