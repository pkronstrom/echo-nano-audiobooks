#include "navigation.h"
#include "content_roots.h"
#include "path.h"
#include "browser.h"
#define B ((u8 *)0x03005f6c)
#define C ((u8 *)0x0300ec1c)
#define H(p) (*(u16 *)(p))
#define W(p) (*(u32 *)(p))
#define post FW(0x0306b040,void,u32)
#define window FW(0x0306b26a,void,u32,const void *)
#define count_folder FW(0x0307974e,int,u32,void *,u32)
#define enumerate FW(0x03079592,void,u32,void *,void *,u32,u32)
static struct content_root roots[8];
static u8 root_count, kind_at[8], pending_kind, chooser_kind, chooser, choice, matches[8], match_count;
u32 navigation_icons[8], navigation_count;
static u8 labels[64];
extern void navigation_dispatch_bridge(void), navigation_strip_bridge(void), navigation_event_bridge(void);
static void branch(u32 address, void (*target)(void))
{
    u32 off=((u32)target&~1u)-address-4, sign=(off>>24)&1;
    H(address)=0xf000|(sign<<10)|((off>>12)&0x3ff);
    H(address+2)=0x9000|((~((off>>23)^sign)&1)<<13)|((~((off>>22)^sign)&1)<<11)|((off>>1)&0x7ff);
}

#include "navigation_icons.inc"
static int read_entry(void *ctx,int exfat,struct media_dir *parent,u32 index,u8 *out)
{
    (void)ctx;fw_wdt();
    return exfat?fw_exfat_entry(out,parent,index):FW(0x0305b3ea,int,u8 *,u32,u32)(out,parent->cluster,index);
}
static u32 scan(void)
{
    fw_lock();int n=content_scan(read_entry,0,FS_TYPE==3,roots,8);fw_unlock();
    root_count=n>0?(u8)n:0;
    u32 kinds=0;for(u32 i=0;i<root_count;i++)kinds|=roots[i].kind;
    return kinds;
}
void navigation_menu_init(void)
{
    chooser=pending_kind=0;
    u32 kinds=scan();navigation_count=6;
    __builtin_memcpy(labels,(void *)0x0300e6d8,48);
    __builtin_memcpy(navigation_icons,(void *)0x03079504,24);
    for(u32 kind=1;kind<=2;kind++)if(kinds&kind){
        u32 n=navigation_count++;kind_at[n]=kind;
        __builtin_memset(labels+n*8,0,8);H(labels+n*8+6)=kind==1?0x83:0x84;
        navigation_icons[n]=(u32)(kind==1?navigation_book_icon:navigation_meditation_icon);
    }
    branch(0x03079b1e,navigation_dispatch_bridge);
    branch(0x030795b4,navigation_strip_bridge);
    /* The overlay reload restores the base literals. Install RAM tables only
     * after the resident loader and bounded scan have both completed. */
    W(0x0307a24c)=(u32)labels;W(0x0307a4d8)=(u32)navigation_icons;
    *(u8 *)0x03079f5e=navigation_count-1;*(u8 *)0x03079f70=navigation_count-1;
    if(H(0x0300e708)>=navigation_count)H(0x0300e708)=0;
    __asm volatile("dsb\nisb" ::: "memory");
}
u32 navigation_menu_dispatch(void)
{
    u32 selected=H(0x0300e708);
    if(selected<6||selected>=navigation_count)return 0;
    u32 kind=kind_at[selected];
    if(!(scan()&kind)){navigation_menu_init();post(51);return 1;}
    pending_kind=kind;
    const u8 args[4]={6,0,0,0};window(9,args);return 1;
}
/* Build native ancestry from raw identities. Each parent cursor uses its
 * visible directory ordinal, so native Back selects the child just left. */
static int install_root(const struct content_root *root)
{
    struct media_ref chain[7];
    fw_lock();int ok=content_root_chain(read_entry,0,FS_TYPE==3,root,chain);fw_unlock();
    if(ok!=1)return 0;
    u32 filter=W(W(B+0x1f4)+4);
    for(u32 level=0;level<=root->depth;level++){
        u8 *record=B+56*level;
        if(level){
            struct media_ref *r=chain+level-1;
            __builtin_memset(record,0,56);W(record+20)=r->cluster;
            W(record+24)=r->cluster;W(record+28)=r->size;record[36]=FS_TYPE==3?r->flags:1;
        }
        count_folder(filter,record+12,3);
        H(B+0x1ce + 2*level)=H(B+0x1de + 2*level)=0;
        if(level<root->depth){
            struct media_dir parent=chain[level].parent;u8 raw[32];u32 ordinal=0;
            fw_lock();
            for(u32 index=0;index<chain[level].index;index++){
                if(read_entry(0,FS_TYPE==3,&parent,index,raw)){fw_unlock();return 0;}
                if(FS_TYPE==3){if(raw[0]==0x85&&(raw[4]&16)&&!(raw[4]&10))ordinal++;}
                else if(raw[0]&&raw[0]!=0xe5&&raw[0]!='.'&&(raw[11]&16)&&!(raw[11]&10))ordinal++;
            }
            fw_unlock();
            H(B+0x1ce + 2*level)=ordinal&~1u;H(B+0x1de + 2*level)=ordinal&1u;
        }
    }
    H(B+0x1cc)=root->depth;H(B+0x1ee)=H(B+0x1f0)=0;H(C+12)=0;
    enumerate(filter,(void *)W(B),B+root->depth*56+12,0,3);
    return 1;
}
static void chooser_draw(void)
{
    u32 page=choice&~1u;H(B+0x1cc)=0;H(B+12)=H(B+16)=match_count;H(B+14)=0;
    H(B+0x1ce)=page;H(B+0x1ee)=H(B+0x1f0)=choice&1;
    H(B+8)=match_count-page>1?2:1;H(C+12)=0;
    u8 *node=(u8 *)W(B);
    for(u32 slot=0;slot<2;slot++,node=(u8 *)W(node+4)){
        __builtin_memset(node+8,0,616);
        if(page+slot>=match_count)continue;
        struct content_root *root=roots+matches[page+slot];
        W(node+12)=matches[page+slot];u16 *name=(u16 *)(node+0x70);u32 used=0;
        struct media_ref chain[7];
        fw_lock();int ok=content_root_chain(read_entry,0,FS_TYPE==3,root,chain);
        if(ok==1){
            for(u32 level=0;level<root->depth;level++){
                u16 *component=playback_path_scratch;struct media_ref ref;struct media_dir parent=chain[level].parent;
                if(media_directory_name(read_entry,0,FS_TYPE==3,&parent,chain[level].cluster,component,&ref)!=1)break;
                if(used<254)name[used++]='/';
                for(u32 n=0;component[n]&&used<254;n++)name[used++]=component[n];
            }
        }
        fw_unlock();if(!used)name[used++]='/';if(used&&name[used-1]>=0xd800&&name[used-1]<=0xdbff)used--;name[used]=0;
    }
    post(333);post(335);
}
void navigation_browser_init(void)
{
    branch(0x0307b31a,navigation_event_bridge);H(0x0307b31e)=0xbf00;
    __asm volatile("dsb\nisb" ::: "memory");
    if(!pending_kind){chooser=0;return;}
    u32 kind=pending_kind;chooser_kind=kind;pending_kind=0;match_count=0;scan();
    for(u32 i=0;i<root_count;i++)if(roots[i].kind&kind)matches[match_count++]=i;
    if(match_count==1&&install_root(roots+matches[0])){post(333);post(335);return;}
    if(match_count>1){chooser=1;choice=0;chooser_draw();return;}
    chooser=0;window(0,0);
}
static int same_root(const struct content_root *a,const struct content_root *b)
{
    for(u32 i=0;i<a->depth;i++)if(a->cluster[i]!=b->cluster[i]||a->index[i]!=b->index[i])return 0;
    return 1;
}
u32 navigation_event(u32 message)
{
    if(!chooser)return 0;
    /* Synthetic nodes never reach stock context/delete/menu actions. */
    if(message==0x20000040||message==0x40001000){chooser=0;window(0,0);return 2;}
    if(message==0x40000040){
        struct content_root saved=roots[matches[choice]];
        u32 kind=chooser_kind;scan();
        for(u32 i=0;i<root_count;i++)if((roots[i].kind&kind)&&roots[i].depth==saved.depth&&
            same_root(roots+i,&saved)){
            if(install_root(roots+i)){chooser=0;post(333);post(335);return 1;}break;
        }
        chooser=0;window(0,0);return 2;
    }
    if(message==0x40000004||message==0x30000004){choice=(choice+1)%match_count;chooser_draw();}
    if(message==0x40000008||message==0x30000008){choice=choice?choice-1:match_count-1;chooser_draw();}
    return 1;
}
