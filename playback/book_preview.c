#include "book_preview.h"
#include "queue.h"
#include "journal.h"
#include "resume.h"
static struct playlist_queue preview;
/* Preview metadata persists; parser input lives only during the synchronous
 * open. A separate guard prevents reentry from replacing the preview queue. */
static struct {
    struct {
        struct media_ref mark_file;
        u32 mark_count,mark_generation,mark_slot,resume_chapter,resume_time;
        int mark_ready;
        u8 rate;
        u32 marks[JOURNAL_BOOKMARK_CAPACITY][2];
    } saved;
} workspace;
static u32 parsing;
#define marks workspace.saved.marks
#define mark_file workspace.saved.mark_file
#define mark_count workspace.saved.mark_count
#define mark_generation workspace.saved.mark_generation
#define mark_slot workspace.saved.mark_slot
#define resume_chapter workspace.saved.resume_chapter
#define resume_time workspace.saved.resume_time
#define mark_ready workspace.saved.mark_ready
#define rate workspace.saved.rate
static u32 sector[128];
static u32 opened;
u32 book_preview_rate(void) { return rate; }
void book_preview_set_rate(u32 q) { rate=q>=4 && q<=8?q:4; }
static int read_file(void *ctx,u32 offset,u8 *out,u32 length)
{
    return playback_read(*(int *)ctx,offset,out,length);
}
static void close_file(int h) { playback_close(h); }
static int lookup(void *ctx,const u16 *path,struct media_ref *ref)
{ (void)ctx;return playback_lookup(path,ref); }
static int read_sector(int h,u32 slot)
{
    u32 used=0;
    while(used<512){int n=read_file(&h,slot*512+used,(u8 *)sector+used,512-used);if(n<=0)return 0;used+=(u32)n;}
    return sector[127]==book_crc(sector,508);
}
static __attribute__((noinline)) void read_resume(const u16 *path)
{
    struct media_ref file;int h=journal_open(path,"RSM",&file);
    if(h<0)return;
    u32 found=0,generation=0,signature=playlist_queue_physical_signature(&preview);
    for(u32 slot=0;slot<2;slot++){
        if(!read_sector(h,slot)||!journal_sector_valid(sector,JOURNAL_RESUME_MAGIC))continue;
        if(found&&(int)(sector[1]-generation)<=0)continue;
        found=1;generation=sector[1];resume_chapter=resume_time=0;rate=4;
        struct media_ref chapter;
        if(sector[2]==signature && sector[3] && playlist_queue_ref(&preview,sector[3]-1,&chapter) &&
           chapter.parent.cluster==sector[5] && chapter.index==sector[6] && chapter.cluster==sector[7]){
            resume_chapter=sector[3];resume_time=sector[4];rate=book_rate(sector[8]);
        }
    }
    close_file(h);
}
static __attribute__((noinline)) int valid_marks(void) { return journal_sector_valid(sector,JOURNAL_BOOKMARK_MAGIC); }
static void read_marks(const u16 *path)
{
    int h=journal_open(path,"BMK",&mark_file);if(h<0)return;
    u32 found=0;
    for(u32 slot=0;slot<2;slot++){
        if(!read_sector(h,slot)||!valid_marks())continue;
        if(found&&(int)(sector[1]-mark_generation)<=0)continue;
        found=1;mark_generation=sector[1];mark_slot=slot;
    }
    if(found && read_sector(h,mark_slot) && (!sector[3]||sector[2]==preview.signature)){
        mark_ready=1;mark_count=sector[3];
        __builtin_memcpy(marks,sector+4,mark_count*8);
    }
    close_file(h);
}
int book_preview_open(const u16 *path)
{
    if(parsing)return -1;
    struct m3u_workspace parser={0};
    u16 base[256];
    opened=0;mark_ready=0;mark_count=0;resume_chapter=resume_time=0;rate=4;
    playlist_queue_clear(&preview);
    u32 length=0,slash=0;
    while(path[length]){
        if(length>=255)return -1;
        base[length]=path[length];if(path[length]=='/')slash=length;length++;
    }
    if(!length||path[0]!='/'||path[length-1]=='/')return -1;
    base[slash?slash:1]=0;
    struct media_ref file;if(playback_lookup(path,&file)!=1)return -1;
    int h=playback_open(&file);if(h<0)return -1;
    struct m3u_stats stats;
    parsing=1;
    int n=playlist_queue_build_with_workspace(&preview,&parser,read_file,lookup,&h,base,&stats);
    parsing=0;
    close_file(h);
    mark_ready=mark_count=0;resume_chapter=resume_time=0;rate=4;
    if(n<=0)return n;
    read_resume(path);read_marks(path);opened=1;return n;
}
int book_preview_ref(u32 index,struct media_ref *out)
{ return opened && playlist_queue_ref(&preview,index,out); }
u32 book_preview_count(void) { return opened?preview.count:0; }
u32 book_preview_signature(void) { return opened?preview.signature:0; }
u32 book_preview_resume(u32 *milliseconds) { *milliseconds=resume_time;return resume_chapter; }
u32 book_preview_marks(void) { return opened?mark_count:0; }
int book_preview_mark(u32 index,u32 entry[2])
{
    if(!opened||index>=mark_count)return 0;
    entry[0]=marks[index][0];entry[1]=marks[index][1];return 1;
}
/* Delete only the journal version the menu displayed. A newly added bookmark
 * invalidates this snapshot instead of allowing an index to target another row. */
int book_preview_delete(u32 index)
{
    if(!opened||!mark_ready||index>=mark_count)return -1;
    if(!journal_try_write())return -1;
    int h=playback_open_update(&mark_file);if(h<0){journal_end_write();return -1;}
    int latest=-1;u32 generation=0;
    for(u32 slot=0;slot<2;slot++){
        if(read_sector(h,slot)&&valid_marks() && (latest<0||(int)(sector[1]-generation)>0)){
            latest=(int)slot;generation=sector[1];
        }
    }
    int result=-1;
    if(latest<0||generation!=mark_generation || !read_sector(h,(u32)latest) ||
       sector[2]!=preview.signature || sector[3]!=mark_count ||
       sector[4+index*2]!=marks[index][0] || sector[5+index*2]!=marks[index][1])goto done;
    for(u32 i=index;i+1<mark_count;i++){
        sector[4+i*2]=sector[6+i*2];sector[5+i*2]=sector[7+i*2];
    }
    u32 count=mark_count-1;sector[4+count*2]=sector[5+count*2]=0;
    sector[1]++;sector[3]=count;sector[127]=book_crc(sector,508);
    fw_lock();u32 wrote=fw_file_write(sector,((u32)latest^1)*512,512,h);fw_unlock();
    if(wrote==512){
        mark_count=count;mark_generation=sector[1];mark_slot=(u32)latest^1;
        __builtin_memcpy(marks,sector+4,count*8);result=1;
    }
 done: close_file(h);journal_end_write();return result;
}
