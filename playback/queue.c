#include "queue.h"
/* Only geometry and identity survive parsing; live metadata is read at play time. */
struct queued_file { u32 parent, length, cluster; u16 index; u8 flags, reserved; };
_Static_assert(sizeof(struct queued_file) == 16, "queue RAM budget");
static struct queued_file tracks[PLAYLIST_CAPACITY];
static u32 count;
struct build_context { m3u_read_fn read; playlist_lookup_fn lookup; void *ctx; };
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
    return b->read(b->ctx, offset, out, length);
}
static int append(void *ctx, const u16 *path, u32 offset)
{
    (void)offset;
    struct build_context *b = ctx;
    if (!playlist_audio_path(path)) return 0;
    struct media_ref ref;
    int r = b->lookup(b->ctx, path, &ref);
    if (r <= 0) return r;
    if ((ref.filesystem == 3 && ref.name_units > 127) ||
        (ref.attrs & 16) || ref.cluster < 2 || ref.index >= 65536 ||
        ref.parent.flags > 255 || count >= PLAYLIST_CAPACITY) return 0;
    tracks[count++] = (struct queued_file){ref.parent.cluster, ref.parent.length,
                                          ref.cluster, ref.index, ref.parent.flags, 0};
    return 1;
}
int playlist_build(m3u_read_fn read, playlist_lookup_fn lookup, void *ctx,
                   const u16 *base, struct m3u_stats *stats)
{
    struct build_context b = {read, lookup, ctx};
    count = 0;
    int r = m3u_scan(read_chunk, append, &b, base, stats);
    if (r) { count = 0; return r; }
    if (count == PLAYLIST_CAPACITY && stats->skipped) stats->limited = 1;
    return (int)count;
}
void playlist_clear(void) { count = 0; }
u32 playlist_count(void) { return count; }
int playlist_ref(u32 index, struct media_ref *ref)
{
    if (index >= count) return 0;
    const struct queued_file *q = &tracks[index];
    *ref = (struct media_ref){.parent={q->parent,q->length,0,q->flags},
                             .index=q->index,.cluster=q->cluster};
    return 1;
}
