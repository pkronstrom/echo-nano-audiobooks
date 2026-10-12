#include "resume.h"
#include "runtime.h"
#include "queue.h"
#include "session.h"
#define MAGIC 0x31524e45u /* ENR1, fixed 512-byte journal sectors */
static struct media_ref record_file;
static u32 sector[128];
static u32 enabled, generation, slot, signature;
u32 book_crc(const void *data,u32 length)
{
    const u8 *p=data; u32 crc=~0u;
    for (u32 i=0;i<length;i++) {
        crc^=p[i];
        for (u32 b=0;b<8;b++) crc=(crc>>1)^(0xedb88320u & (0u-(crc&1)));
    }
    return ~crc;
}
static int valid(void) { return sector[0]==MAGIC && sector[127]==book_crc(sector,508); }
static int read_sector(int h,u32 which)
{
    u32 got=0;
    while (got<512) {
        int n=playback_read(h,which*512+got,(u8 *)sector+got,512-got);
        if (n<=0) return 0;
        got+=(u32)n;
    }
    return 1;
}
static u32 queue_signature(void)
{
    u32 hash=2166136261u;
    for (u32 n=0;n<playlist_count();n++) {
        struct media_ref ref; playlist_ref(n,&ref);
        u32 values[]={ref.parent.cluster,ref.index,ref.cluster};
        for (u32 j=0;j<3;j++) hash=(hash^values[j])*16777619u;
    }
    return hash;
}
void book_clear(void) { enabled=0; }
u32 book_load(const u16 *playlist,u32 *milliseconds)
{
    enabled=0; *milliseconds=0;
    u16 path[256]; u32 n=0;
    while (n<255 && playlist[n]) { path[n]=playlist[n]; n++; }
    if (n<4 || playlist[n]) return 0;
    path[n]=0; path[n-3]='R';path[n-2]='S';path[n-1]='M';
    if (playback_lookup(path,&record_file)!=1 || record_file.size!=1024) return 0;
    int h=playback_open(&record_file);
    if (h<0) return 0;
    u32 position=0,ms=0; signature=queue_signature();
    for (u32 i=0;i<2;i++) {
        if (!read_sector(h,i)) { enabled=0; break; }
        if (!valid()) continue;
        if (!enabled || (int)(sector[1]-generation)>0) {
            enabled=1; generation=sector[1];slot=i;
            position=0;ms=0;
            struct media_ref chapter;
            if (sector[2]==signature && sector[3] &&
                playlist_ref(sector[3]-1,&chapter) &&
                chapter.parent.cluster==sector[5] && chapter.index==sector[6] && chapter.cluster==sector[7]) {
                position=sector[3];ms=sector[4];
            }
        }
    }
    playback_close(h);
    if (!enabled) return 0;
    *milliseconds=ms;
    return position;
}
void book_save(void)
{
    if (!enabled || !playback_active) return;
    const u16 *state=(const u16 *)0x0300d85c;
    u32 position=state[1]; struct media_ref chapter;
    if (!position || !playlist_ref(position-1,&chapter)) return;
    /* Verify selected identity: stock save may later rebase its folder index. */
    const u8 *raw=(const u8 *)state+0x14;
    u32 cluster=((u32)raw[20]|(u32)raw[21]<<8)<<16|raw[26]|(u32)raw[27]<<8;
    if (cluster!=chapter.cluster) return;
    const u32 *info=*(const u32 *volatile *)0x03039714;
    if ((u32)info!=0x03023090) return;
    u32 ms=info[1]; if (ms>info[0]) ms=info[0];
    int h=playback_open_update(&record_file);
    if (h<0) return;
    /* Revalidate the existing companion before every write. */
    if (!read_sector(h,slot) || !valid()) { playback_close(h);return; }
    __builtin_memset(sector,0,sizeof(sector));
    sector[0]=MAGIC;sector[1]=generation+1;sector[2]=signature;sector[3]=position;sector[4]=ms;
    sector[5]=chapter.parent.cluster;sector[6]=chapter.index;sector[7]=chapter.cluster;
    sector[127]=book_crc(sector,508);
    u32 next=slot^1;
    u32 written=fw_file_write(sector,next*512,512,h);
    playback_close(h);
    if (written==512) { slot=next;generation++; }
}
