#include "queue.h"
static struct playlist_queue active_queue;
_Static_assert(sizeof(struct playlist_queue)==3848,"queue RAM budget");
struct build_context {
    m3u_read_fn read;
    playlist_lookup_fn lookup;
    void *ctx;
    u32 hash;
    struct playlist_queue *queue;
};
int playlist_audio_path(const u16 *path)
{
    const u16 *ext = 0;
    for (; *path; path++) {
        if (*path == '/') ext = 0;
        else if (*path == '.') ext = path+1;
    }
    if (!ext) return 0;
    /* Match full suffixes, including conventional long names for stock codecs. */
    static const char extensions[] = "mp1\0mp2\0mp3\0wma\0wav\0ape\0fla\0flac\0aac\0m4a\0ogg\0mp4\0" "3gp\0dff\0dsf\0";
    for (const char *p = extensions; *p;) {
        u32 i = 0;
        while (p[i] && ext[i]) {
            u16 c = ext[i];
            if (c >= 'A' && c <= 'Z') c += 32;
            if (c != (u8)p[i]) break;
            i++;
        }
        if (!p[i] && !ext[i]) return 1;
        while (*p++) {}
    }
    return 0;
}
static int read_chunk(void *ctx, u32 offset, u8 *out, u32 length)
{
    struct build_context *b = ctx;
    int n=b->read(b->ctx,offset,out,length);
    if (n>0 && (u32)n<=length)
        for (int i=0;i<n;i++) b->hash=(b->hash^out[i])*16777619u;
    return n;
}
static int append(void *ctx, const u16 *path, u32 offset)
{
    struct build_context *b = ctx;
    if (!playlist_audio_path(path)) return 0;
    struct playlist_queue *q = b->queue;
    struct media_ref ref;
    int r = b->lookup(b->ctx, path, &ref);
    if (r <= 0) return r;
    if ((ref.filesystem == 3 && ref.name_units > 127) ||
        (ref.attrs & 16) || ref.cluster < 2 || ref.index >= 65536 ||
        ref.parent.flags > 255 || q->count >= PLAYLIST_CAPACITY) return 0;
    q->tracks[q->count] = (struct queued_file){ref.parent.cluster,ref.parent.length,ref.cluster};
    q->indices[q->count]=ref.index;q->flags[q->count]=ref.parent.flags;q->count++;
    q->signature=(q->signature^offset)*16777619u;
    return 1;
}
int playlist_queue_build_with_workspace(struct playlist_queue *queue,
                         struct m3u_workspace *workspace, m3u_read_fn read,
                         playlist_lookup_fn lookup, void *ctx,
                         const u16 *base, struct m3u_stats *stats)
{
    struct build_context b = {read, lookup, ctx,2166136261u,queue};
    queue->count = 0;queue->signature=2166136261u;
    int r = workspace ? m3u_scan_with_workspace(workspace, read_chunk, append, &b, base, stats)
                      : m3u_scan(read_chunk, append, &b, base, stats);
    if (r) { queue->count = 0; return r; }
    if (queue->count == PLAYLIST_CAPACITY && stats->skipped) stats->limited = 1;
    queue->signature^=b.hash;
    return (int)queue->count;
}
int playlist_queue_build(struct playlist_queue *queue, m3u_read_fn read,
                         playlist_lookup_fn lookup, void *ctx,
                         const u16 *base, struct m3u_stats *stats)
{ return playlist_queue_build_with_workspace(queue,0,read,lookup,ctx,base,stats); }
void playlist_queue_clear(struct playlist_queue *q) { q->count = 0; }
u32 playlist_queue_count(const struct playlist_queue *q) { return q->count; }
u32 playlist_queue_signature(const struct playlist_queue *q)
{ return q->count?q->signature:0; }
int playlist_queue_ref(const struct playlist_queue *queue, u32 index, struct media_ref *ref)
{
    if (index >= queue->count) return 0;
    const struct queued_file *q = &queue->tracks[index];
    *ref = (struct media_ref){.parent={q->parent,q->length,0,queue->flags[index]},
                             .index=queue->indices[index],.cluster=q->cluster};
    return 1;
}
int playlist_build(m3u_read_fn read, playlist_lookup_fn lookup, void *ctx,
                   const u16 *base, struct m3u_stats *stats)
{ return playlist_queue_build(&active_queue,read,lookup,ctx,base,stats); }
void playlist_clear(void) { playlist_queue_clear(&active_queue); }
u32 playlist_count(void) { return playlist_queue_count(&active_queue); }
u32 playlist_signature(void) { return playlist_queue_signature(&active_queue); }
int playlist_ref(u32 index, struct media_ref *ref)
{ return playlist_queue_ref(&active_queue,index,ref); }

u32 playlist_queue_physical_signature(const struct playlist_queue *queue)
{
    u32 hash=2166136261u;
    for(u32 n=0;n<queue->count;n++){
        u32 values[]={queue->tracks[n].parent,queue->indices[n],queue->tracks[n].cluster};
        for(u32 j=0;j<3;j++)hash=(hash^values[j])*16777619u;
    }
    return hash;
}
u32 playlist_physical_signature(void) { return playlist_queue_physical_signature(&active_queue); }
