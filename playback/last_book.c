#include "book_menu.h"
#include "last_book.h"
#include "queue.h"
static u16 last_path[256];
struct saved_file { u32 parent,index,cluster,size; };
static struct saved_file last_ref;
static u32 signature;
static u8 valid,device,filesystem;
void last_book_remember(const u16 *path)
{
    u32 n=0;while(n<256 && path[n])n++;
    if(!n || n>=256 || path[0]!='/')return;
    struct media_ref ref;
    if(playback_lookup(path,&ref)!=1 || (ref.attrs&16))return;
    fw_lock();
    __builtin_memcpy(last_path,path,(n+1)*2);last_ref=(struct saved_file){ref.parent.cluster,ref.index,ref.cluster,ref.size};
    signature=playlist_signature();
    device=*(const u8 *)0x0300d173;filesystem=FS_TYPE;valid=1;fw_unlock();
}
int last_book_snapshot(u16 *out,u32 *saved_signature)
{
    out[0]=0;fw_lock();
    if(!valid || device!=*(const u8 *)0x0300d173 || filesystem!=FS_TYPE){fw_unlock();return 0;}
    struct saved_file saved=last_ref;
    if(saved_signature)*saved_signature=signature;
    __builtin_memcpy(out,last_path,sizeof last_path);fw_unlock();
    struct media_ref ref;
    if(playback_lookup(out,&ref)!=1 || (ref.attrs&16) ||
       ref.parent.cluster!=saved.parent || ref.index!=saved.index ||
       ref.cluster!=saved.cluster || ref.size!=saved.size){out[0]=0;return 0;}
    return 1;
}
int last_book_get(u16 *out) { return last_book_snapshot(out,0); }
/* The landing already validated this identity. Format its cached path without
 * another directory scan; the native row owns exactly256 UTF-16 code units. */
void last_book_label(u16 out[256])
{
    u16 *limit=out+255;
    fw_lock();
    const u16 *name=last_path+1,*parent=name,*end=name;
    for(const u16 *p=name;*p;p++){
        if(*p=='/'){parent=name;name=p+1;}
        end=p+1;
    }
    if(end-name==8 && parent!=name && (name[0]|32)=='b' &&
       (name[1]|32)=='o' && (name[2]|32)=='o' && (name[3]|32)=='k'){
        end=name-1;name=parent;
    }else if(end-name>4)end-=4;
    out=book_text(out,"Continue ");
    while(name<end && out<limit)*out++=*name++;
    if(out[-1]>=0xd800 && out[-1]<=0xdbff)out--;
    *out=0;fw_unlock();
}
