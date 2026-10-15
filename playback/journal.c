#include "journal.h"
#include "resume.h"
#include "queue.h"
int journal_read_sector(int h,u32 slot)
{
    u32 got=0;
    while (got<512) {
        int n=playback_read(h,slot*512+got,(u8 *)playback_scratch+got,512-got);
        if (n<=0 || (u32)n>512-got) return 0;
        got+=(u32)n;
    }
    return 1;
}
int journal_open(const u16 *playlist,const char *extension,struct media_ref *ref)
{
    u16 path[256];u32 n=0;
    while (n<255 && playlist[n]) { path[n]=playlist[n];n++; }
    if (n<4 || playlist[n]) return -1;
    path[n]=0;
    for (u32 i=0;i<3;i++) path[n-3+i]=(u8)extension[i];
    if (playback_lookup(path,ref)!=1 || ref->size!=1024) return -1;
    return playback_open(ref);
}
/* UI deletion and player bookmark append share a nonblocking transaction guard.
 * Never wait with decoder IRQs masked; a busy operation is retried by its caller. */
static u32 writer;
int journal_try_write(void) { return !__atomic_exchange_n(&writer,1,__ATOMIC_ACQUIRE); }
void journal_end_write(void) { __atomic_store_n(&writer,0,__ATOMIC_RELEASE); }

int journal_sector_valid(const u32 *sector,u32 magic)
{
    if(sector[0]!=magic || sector[127]!=book_crc(sector,508))return 0;
    if(magic==JOURNAL_BOOKMARK_MAGIC){
        if(sector[3]>JOURNAL_BOOKMARK_CAPACITY)return 0;
        for(u32 i=0;i<sector[3];i++)
            if(!sector[4+i*2]||sector[4+i*2]>PLAYLIST_CAPACITY)return 0;
    }
    return 1;
}
