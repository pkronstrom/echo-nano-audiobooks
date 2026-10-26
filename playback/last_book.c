#include "book_menu.h"
#include "last_book.h"
#include "queue.h"
#include "content_roots.h"
#include "journal.h"
#include "resume.h"
#include "session.h"
#include "browser.h"
static u16 last_path[256];
struct saved_file { u32 parent,index,cluster,size; };
static struct saved_file last_ref;
static u32 signature;
static u8 valid,device,filesystem;
static u8 scanned;
static u32 sequence;
u32 book_selection;
static int read_entry(void *ctx,int fs,struct media_dir *parent,u32 index,u8 *out)
{
    (void)ctx;fw_wdt();
    return fs?fw_exfat_entry(out,parent,index):FW(0x0305b3ea,int,u8 *,u32,u32)(out,parent->cluster,index);
}
static int discover(void *context,const struct content_root *chain,const struct media_ref *file)
{
    u32 *best=context;
    if(file->size!=1024)return 0;
    int h=playback_open(file);if(h<0)return -1;
    u32 chosen[16]={0},found=0;
    for(u32 i=0;i<2;i++){
        if(!journal_read_sector(h,i)){playback_close(h);return -1;}
        u32 *s=playback_scratch;
        if(journal_sector_valid(s,JOURNAL_RESUME_MAGIC) && (!found || (int)(s[1]-chosen[1])>0)){
            __builtin_memcpy(chosen,s,sizeof chosen);found=1;
        }
    }
    playback_close(h);
    if(!found || chosen[9]!=LAST_BOOK_TAG || !chosen[10])return 0;
    if(!sequence || (int)(chosen[10]-sequence)>0)sequence=chosen[10];
    if(*best && (int)(chosen[10]-*best)<=0)return 0;
    u16 component[256],path[256];
    struct media_dir parent={0};struct media_ref ref;
    u32 used=0;
    for(u32 level=0;level<=chain->depth;level++){
        int ok=level==chain->depth ? media_entry_name(read_entry,0,FS_TYPE==3,&parent,file->index,component,&ref) :
            media_directory_name(read_entry,0,FS_TYPE==3,&parent,chain->cluster[level],component,&ref);
        if(ok!=1)return -1;
        if(used>=254)return 0;
        path[used++]='/';
        for(u32 i=0;component[i];i++){if(used>=255)return 0;path[used++]=component[i];}
        parent=(struct media_dir){ref.cluster,ref.size,0,ref.flags};
    }
    path[used]=0;
    if(used<5 || path[used-4]!='.' || (path[used-3]|32)!='r' ||
       (path[used-2]|32)!='s' || (path[used-1]|32)!='m')return 0;
    path[used-3]='M';path[used-2]='3';path[used-1]='U';
    int lookup=playback_lookup(path,&ref);
    if(lookup<0)return -1;
    if(!lookup || (ref.attrs&16) || ref.parent.cluster!=chosen[11] ||
       ref.index!=chosen[12] || ref.cluster!=chosen[13] || ref.size!=chosen[14])return 0;
    __builtin_memcpy(last_path,path,(used+1)*2);
    last_ref=(struct saved_file){ref.parent.cluster,ref.index,ref.cluster,ref.size};
    signature=chosen[15];*best=chosen[10];return 0;
}
void last_book_restore_roots(const struct content_root *roots,u32 count)
{
    u8 dev=*(const u8 *)0x0300d173,fs=FS_TYPE;
    if(scanned && device==dev && filesystem==fs)return;
    if(playback_scratch_busy)return;
    playback_scratch_busy=1;valid=scanned=0;sequence=0;
    u32 best=0;int result=0;
    fw_lock();
    for(u32 i=0;i<count;i++)if(roots[i].kind&1){
        result=content_walk(read_entry,0,fs==3,roots+i,discover,&best);
        if(result<0 || !(result&1)){result=-1;break;}
    }
    if(result>=0 && dev==*(const u8 *)0x0300d173 && fs==FS_TYPE){
        device=dev;filesystem=fs;scanned=1;valid=best!=0;
    }else sequence=0;
    fw_unlock();playback_scratch_busy=0;
}
void last_book_restore(void)
{
    if(scanned && device==*(const u8 *)0x0300d173 && filesystem==FS_TYPE)return;
    scanned=0;sequence=0;
    struct content_root roots[8];
    fw_lock();int count=content_scan(read_entry,0,FS_TYPE==3,roots,8);fw_unlock();
    if(count>=0)last_book_restore_roots(roots,count);
}
void last_book_record(u32 sector[128])
{
    if(!book_selection)return;
    struct media_ref ref;
    if(playback_lookup(playback_book_path(),&ref)!=1 || (ref.attrs&16))return;
    sector[9]=LAST_BOOK_TAG;sector[10]=book_selection;
    sector[11]=ref.parent.cluster;sector[12]=ref.index;
    sector[13]=ref.cluster;sector[14]=ref.size;sector[15]=playlist_signature();
}
void last_book_remember(const u16 *path)
{
    u32 n=0;while(n<256 && path[n])n++;
    if(!n || n>=256 || path[0]!='/')return;
    struct media_ref ref;
    if(playback_lookup(path,&ref)!=1 || (ref.attrs&16))return;
    last_book_restore();
    fw_lock();
    __builtin_memcpy(last_path,path,(n+1)*2);last_ref=(struct saved_file){ref.parent.cluster,ref.index,ref.cluster,ref.size};
    signature=playlist_signature();
    device=*(const u8 *)0x0300d173;filesystem=FS_TYPE;valid=1;fw_unlock();
    if(scanned){if(!++sequence)sequence=1;book_selection=sequence;}
    else book_selection=0;
}
int last_book_snapshot(u16 *out,u32 *saved_signature)
{
    if(!valid)last_book_restore();
    out[0]=0;fw_lock();
    if(!valid || device!=*(const u8 *)0x0300d173 || filesystem!=FS_TYPE){fw_unlock();return 0;}
    struct saved_file saved=last_ref;
    if(saved_signature)*saved_signature=signature;
    __builtin_memcpy(out,last_path,512);fw_unlock();
    struct media_ref ref;
    if(playback_lookup(out,&ref)!=1 || (ref.attrs&16) ||
       ref.parent.cluster!=saved.parent || ref.index!=saved.index ||
       ref.cluster!=saved.cluster || ref.size!=saved.size){out[0]=0;return 0;}
    return 1;
}
int last_book_get(u16 *out) { return last_book_snapshot(out,0); }
/* The landing already validated this identity. Format its cached path without
 * another directory scan; the native row owns exactly256 UTF-16 code units. */
void book_path_title(const u16 *path,u16 *out,u32 capacity)
{
    u16 *start=out,*limit=out+capacity-1;
    fw_lock();
    const u16 *name=path+1,*parent=name,*end=name;
    for(const u16 *p=name;*p;p++){
        if(*p=='/'){parent=name;name=p+1;}
        end=p+1;
    }
    if(end-name==8 && parent!=name && (name[0]|32)=='b' &&
       (name[1]|32)=='o' && (name[2]|32)=='o' && (name[3]|32)=='k'){
        end=name-1;name=parent;
    }else if(end-name>4)end-=4;
    while(name<end && out<limit)*out++=*name++;
    if(out>start && out[-1]>=0xd800 && out[-1]<=0xdbff)out--;
    *out=0;fw_unlock();
}
void last_book_label(u16 out[256])
{ book_path_title(last_path,book_text(out,"Continue "),247); }
