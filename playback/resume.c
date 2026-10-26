#include "resume.h"
#include "bookmarks.h"
#include "journal.h"
#include "runtime.h"
#include "queue.h"
#include "session.h"
#include "speed.h"
#include "last_book.h"
#define MAGIC JOURNAL_RESUME_MAGIC /* ENR1, fixed 512-byte journal sectors */
static struct media_ref record_file;
#define sector (*(u32 (*)[128])playback_scratch)
static u32 enabled, generation, slot, signature;
static u32 saved_tick;
static u32 saved_selection;
#define SAVE_TICKS (*(volatile u32 *)0x0300d144)
void book_autosave(void)
{
    struct media_ref ref;u32 ms;
    if(saved_selection!=book_selection && !playback_position(&ref,&ms))return;
    if (saved_selection!=book_selection || (u32)(SAVE_TICKS-saved_tick)>=30000) {
        saved_selection=book_selection;
        saved_tick=SAVE_TICKS; /* Failed I/O must not become a tight retry loop. */
        book_save();
    }
}
u32 book_crc(const void *data,u32 length)
{
    const u8 *p=data; u32 crc=~0u;
    for (u32 i=0;i<length;i++) {
        crc^=p[i];
        for (u32 b=0;b<8;b++) crc=(crc>>1)^(0xedb88320u & (0u-(crc&1)));
    }
    return ~crc;
}
static __attribute__((noinline)) int valid(void) { return journal_sector_valid(sector,MAGIC); }
void book_clear(void) { enabled=0;playback_cancel_bookmark();bookmarks_clear(); }
u32 book_load(const u16 *playlist,u32 *milliseconds)
{
    *milliseconds=0;playback_speed_set(4);saved_tick=SAVE_TICKS;
    book_selection=saved_selection=0;
    if (playback_scratch_busy) return 0;
    enabled=0;
    int h=journal_open(playlist,"RSM",&record_file);
    if (h<0) return 0;
    u32 position=0,ms=0,rate=4; signature=playlist_physical_signature();
    for (u32 i=0;i<2;i++) {
        if (!journal_read_sector(h,i)) { enabled=0; break; }
        if (!valid()) continue;
        if (!enabled || (int)(sector[1]-generation)>0) {
            enabled=1; generation=sector[1];slot=i;
            position=0;ms=0;rate=4;
            book_selection=0;
            struct media_ref chapter;
            if (sector[2]==signature && sector[3] &&
                playlist_ref(sector[3]-1,&chapter) &&
                chapter.parent.cluster==sector[5] && chapter.index==sector[6] && chapter.cluster==sector[7]) {
                position=sector[3];ms=sector[4];rate=book_rate(sector[8]);
                if(sector[9]==LAST_BOOK_TAG)book_selection=sector[10];
            }
        }
    }
    playback_close(h);
    if (!enabled) return 0;
    playback_speed_set(rate);
    saved_selection=book_selection;
    *milliseconds=ms;
    return position;
}
void book_save(void)
{
    if (playback_scratch_busy || !enabled || playback_active!=1) return;
    struct media_ref chapter;u32 ms;
    u32 position=playback_position(&chapter,&ms);
    if (!position) return;
    int h=playback_open_update(&record_file);
    if (h<0) return;
    /* Revalidate the existing companion before every write. */
    if (!journal_read_sector(h,slot) || !valid()) { playback_close(h);return; }
    __builtin_memset(sector,0,sizeof(sector));
    sector[0]=MAGIC;sector[1]=generation+1;sector[2]=signature;sector[3]=position;sector[4]=ms;
    sector[5]=chapter.parent.cluster;sector[6]=chapter.index;sector[7]=chapter.cluster;
    sector[8]=BOOK_SPEED_TAG+playback_speed_launched();
    last_book_record(sector);
    sector[127]=book_crc(sector,508);
    u32 next=slot^1;
    fw_lock();u32 written=fw_file_write(sector,next*512,512,h);fw_unlock();
    playback_close(h);
    if (written==512) { slot=next;generation++;saved_tick=SAVE_TICKS; }
}
