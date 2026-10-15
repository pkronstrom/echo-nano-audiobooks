#include "bookmarks.h"
#include "journal.h"
#include "runtime.h"
#include "resume.h"
#include "queue.h"
#define SECTOR ((u32 *)playback_scratch)
#define MAGIC JOURNAL_BOOKMARK_MAGIC
#define CAPACITY JOURNAL_BOOKMARK_CAPACITY
static struct media_ref companion;
static u32 fingerprint, ready;

void bookmarks_clear(void) { ready=0; }

/* Reload on every operation: no in-RAM bookmark list to become stale. */
static int sector_read(int h,u32 slot)
{
    if (!journal_read_sector(h,slot)) return 0;
    return journal_sector_valid(SECTOR,MAGIC);
}
static int latest(int h)
{
    int slot=-1;u32 generation=0;
    for (u32 i=0;i<2;i++) {
        if (sector_read(h,i) && (slot<0 || (int)(SECTOR[1]-generation)>0)) {
            slot=(int)i;generation=SECTOR[1];
        }
    }
    if (slot<0 || !sector_read(h,(u32)slot)) return -1;
    /* A changed nonempty playlist must not silently retarget bookmarks. */
    if (SECTOR[3] && SECTOR[2]!=fingerprint) return -1;
    return slot;
}
int bookmarks_open(const u16 *playlist,u32 signature)
{
    ready=0;
    if (playback_scratch_busy) return -1;
    fingerprint=signature;
    int h=journal_open(playlist,"BMK",&companion);
    if (h<0) return -1;
    int slot=latest(h);playback_close(h);
    if (slot<0) return -1;
    ready=1;return (int)SECTOR[3];
}
int bookmarks_get(u32 index,u32 entry[2])
{
    if (!ready || playback_scratch_busy) return -1;
    int h=playback_open(&companion);
    if (h<0) return -1;
    int slot=latest(h);playback_close(h);
    if (slot<0 || index>=SECTOR[3]) return -1;
    entry[0]=SECTOR[4+index*2];entry[1]=SECTOR[5+index*2];return 1;
}
int bookmarks_change(u32 index,u32 chapter,u32 milliseconds)
{
    if (!ready || playback_scratch_busy || chapter>PLAYLIST_CAPACITY) return -1;
    if(!journal_try_write())return -1;
    int h=playback_open_update(&companion);
    if (h<0) {journal_end_write();return -1;}
    int slot=latest(h),result=-1;
    if (slot<0) goto done;
    u32 count=SECTOR[3];
    if (index==~0u && chapter) {
        if (count==CAPACITY) goto done;
        SECTOR[4+count*2]=chapter;SECTOR[5+count*2]=milliseconds;
        count++;
    } else if (!chapter && index<count) {
        for (u32 i=index;i+1<count;i++) {
            SECTOR[4+i*2]=SECTOR[6+i*2];SECTOR[5+i*2]=SECTOR[7+i*2];
        }
        count--;SECTOR[4+count*2]=0;SECTOR[5+count*2]=0;
    } else goto done;
    SECTOR[1]++;SECTOR[2]=fingerprint;SECTOR[3]=count;
    SECTOR[127]=book_crc(SECTOR,508);
    fw_lock();u32 wrote=fw_file_write(SECTOR,((u32)slot^1)*512,512,h);fw_unlock();
    if(wrote==512)result=(int)count;
 done:
    playback_close(h);journal_end_write();return result;
}
