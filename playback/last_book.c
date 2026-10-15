#include "last_book.h"
#include "queue.h"
static u16 last_path[256];
static struct media_ref last_ref;
static u32 signature;
static u8 valid,device,filesystem;
void last_book_remember(const u16 *path)
{
    u32 n=0;while(n<256 && path[n])n++;
    if(!n || n>=256 || path[0]!='/')return;
    struct media_ref ref;
    if(playback_lookup(path,&ref)!=1 || (ref.attrs&16))return;
    fw_lock();
    __builtin_memcpy(last_path,path,(n+1)*2);last_ref=ref;
    signature=playlist_signature();
    device=*(const u8 *)0x0300d173;filesystem=FS_TYPE;valid=1;fw_unlock();
}
int last_book_snapshot(u16 *out,u32 *saved_signature)
{
    out[0]=0;fw_lock();
    if(!valid || device!=*(const u8 *)0x0300d173 || filesystem!=FS_TYPE){fw_unlock();return 0;}
    struct media_ref saved=last_ref;
    if(saved_signature)*saved_signature=signature;
    __builtin_memcpy(out,last_path,sizeof last_path);fw_unlock();
    struct media_ref ref;
    if(playback_lookup(out,&ref)!=1 || (ref.attrs&16) ||
       ref.parent.cluster!=saved.parent.cluster || ref.index!=saved.index ||
       ref.cluster!=saved.cluster || ref.size!=saved.size){out[0]=0;return 0;}
    return 1;
}
int last_book_get(u16 *out) { return last_book_snapshot(out,0); }
