#include "runtime.h"
#include "queue.h"
#include "browser.h"
#define native_fat_entry FW(0x0305b3ea, int, u8 *, u32, u32)
#define native_fat_open FW(0x0305be12, int, u8 *, u32, u32, u32, const char *)
#define native_exfat_open FW(0x0305c102, int, u8 *, const void *, u32, u32, const char *)
#define native_read FW(FREAD_ADDR, u32, void *, u32, u32)

static int directory_read(void *ctx, int exfat, struct media_dir *parent,
                           u32 index, u8 *out)
{
    (void)ctx;
    fw_wdt();
    return exfat ? fw_exfat_entry(out, parent, index) :
                   native_fat_entry(out, parent->cluster, index);
}
int playback_lookup(const u16 *path, struct media_ref *ref)
{
    fw_lock();
    int r = media_resolve(directory_read, 0, FS_TYPE == 3, path, ref);
    fw_unlock();
    return r;
}
static u32 word(const u8 *p)
{
    return p[0] | (u32)p[1] << 8 | (u32)p[2] << 16 | (u32)p[3] << 24;
}
/* Caller holds the FS lock. In addition to stale-entry checks, protect stock
 * exFAT indexed-open's 256-byte UTF-16 scratch buffer (127 units plus NUL).
 * Re-read the live stream: a file may have changed after the queue was built. */
static int safe_entry(const struct media_ref *ref, struct media_dir *parent)
{
    u8 raw[32];
    if (ref->index >= 65536 || directory_read(0, FS_TYPE == 3, parent, ref->index, raw)) return 0;
    if (FS_TYPE == 3) {
        if (raw[0] != 0x85 || raw[1] < 2 || (raw[4] & 24) ||
            directory_read(0, 1, parent, ref->index+1, raw)) return 0;
        return raw[0] == 0xc0 && raw[3] && raw[3] <= 127 &&
               !word(raw+12) && !word(raw+28) && word(raw+8) <= word(raw+24) &&
               word(raw+20) == ref->cluster;
    }
    return raw[0] && raw[0] != 0xe5 && !(raw[11] & 24) &&
           ((u32)raw[20] << 16 | (u32)raw[21] << 24 | raw[26] | (u32)raw[27] << 8) == ref->cluster;
}
static int open_mode(const struct media_ref *ref, const char *mode)
{
    if (ref->attrs & 16) return -1;
    u8 name[12];
    struct media_dir parent = ref->parent;
    fw_lock();
    /* Seed the stock shared directory cursor with full parent size/flags.
     * The native exFAT indexed-open wrapper only forwards cluster and flags. */
    int valid = safe_entry(ref, &parent);
    int h = -1;
    if (valid) h = FS_TYPE == 3 ? native_exfat_open(name, &parent, ref->index, 3, mode) :
                              native_fat_open(name, parent.cluster, ref->index, 3, mode);
    fw_unlock();
    return h >= 0 && h < NFILES ? h : -1;
}
int playback_open(const struct media_ref *ref) { return open_mode(ref, "R"); }
int playback_open_update(const struct media_ref *ref)
{
    if (ref->size != 1024 || (ref->attrs & 1)) return -1;
    int handle = open_mode(ref, "RW");
    if (handle >= 0 && word(FILES+handle*FILE_SIZE+16) != 1024) {
        playback_close(handle); return -1;
    }
    return handle;
}
int playback_read(int handle, u32 offset, u8 *out, u32 length)
{
    if(handle<0||handle>=NFILES)return -1;
    fw_lock();
    int result=-1;
    if(!fw_fseek(offset,0,handle)){
        u32 got=native_read(out,length,handle);
        if(got<=length)result=(int)got;
    }
    fw_unlock();return result;
}
void playback_close(int handle)
{
    if(handle>=0&&handle<NFILES){fw_lock();fw_file_close(handle);fw_unlock();}
}
extern u8 __play_bss_start[], __play_bss_end[];
u32 playback_init(void)
{
    __builtin_memset(__play_bss_start, 0, __play_bss_end - __play_bss_start);
    return 0x32504e45; /* ENP2 */
}

/* Ask the stock enumerator for exactly this raw entry, on temporary state. It
 * creates the codec's usual 8.3 alias and exFAT metadata; never accept its next
 * matching file if the saved entry has since disappeared. */
#define native_next FW(0x0305dd8c, int, void *, void *, const char *, u32)
static const char audio_extensions[] = "MP1MP2MP3WMAWAVAPEFLAAACM4AOGGMP43GPDFFDSF";
int playback_select_ref(const struct media_ref *ref, u8 *state, u32 position, u32 count)
{
    if (!position || position > count || count > 512 || ref->index >= 65536) return -1;
    u8 entry[32];
    u32 descriptor[11] = {ref->parent.cluster, ref->index};
    __builtin_memcpy(descriptor+7, &ref->parent, sizeof(ref->parent));
    fw_lock();
    struct media_dir parent = ref->parent;
    int r = safe_entry(ref, &parent) ? native_next(entry, descriptor, audio_extensions, 3) : -1;
    fw_unlock();
    if (r) return -1;
    u32 cluster = ((u32)entry[20] | (u32)entry[21] << 8) << 16 |
                   entry[26] | (u32)entry[27] << 8;
    if (descriptor[1] != ref->index+1 || cluster != ref->cluster || (entry[11] & 16)) return -1;
    __builtin_memcpy(state+0x14, entry, sizeof(entry));
    __builtin_memcpy(state+0x34, descriptor, sizeof(descriptor));
    u16 *s = (u16 *)state;
    s[0] = count; s[1] = position; s[3] = position; s[4] = count;
    s[5] = 2; s[6] = 0; /* listed order, bounded to this queue */
    return 0;
}

static int playlist_read(void *ctx, u32 offset, u8 *out, u32 length)
{
    return playback_read(*(int *)ctx, offset, out, length);
}
static int playlist_lookup(void *ctx, const u16 *path, struct media_ref *ref)
{
    (void)ctx;
    return playback_lookup(path, ref);
}
int playback_load_playlist(const u16 *path, struct m3u_stats *stats)
{
    playlist_clear();
    __builtin_memset(stats, 0, sizeof(*stats));
    u16 *base = playback_path_scratch;
    u32 length = 0, slash = 0;
    while (path[length]) {
        if (length >= M3U_PATH_UNITS-1) return -1;
        base[length] = path[length];
        if (path[length] == '/') slash = length;
        length++;
    }
    if (!length || path[0] != '/' || path[length-1] == '/') return -1;
    base[slash ? slash : 1] = 0;
    struct media_ref ref;
    int r = playback_lookup(path, &ref);
    if (r != 1) return r < 0 ? r : -1;
    int handle = playback_open(&ref);
    if (handle < 0) return -1;
    r = playlist_build(playlist_read, playlist_lookup, &handle, base, stats);
    playback_close(handle);
    return r;
}
/* Selection is separate from load so a failed/empty playlist cannot replace
 * the decoder state. Missing/stale entries are skipped, at most one full lap. */
int playback_playlist_move(u8 *state, int direction, int wrap)
{
    u32 count = playlist_count();
    if (!count) return 19;
    u32 position = ((u16 *)state)[1];
    if (!position || position > count) position = direction < 0 ? 1 : count;
    if (!direction) position = count; /* start at first listed track */
    for (u32 tried = 0; tried < count; tried++) {
        if (!wrap && direction && (direction < 0 ? position == 1 : position == count)) return 19;
        position = direction < 0 ? (position == 1 ? count : position-1) :
                                  (position == count ? 1 : position+1);
        struct media_ref ref;
        playlist_ref(position-1, &ref);
        if (!playback_select_ref(&ref, state, position, count)) return 0;
    }
    return 19;
}

int playback_playlist_step(u8 *state, int direction)
{
    return playback_playlist_move(state, direction, 1);
}

int playback_browser_path(const u8 *node, u16 *out)
{
    fw_lock();
    u32 root = word((const u8 *)0x03076b30+13);
    int result = media_browser_path(directory_read, 0, FS_TYPE == 3,
                        (const u8 *)0x03005f6c, node, root, out);
    fw_unlock();
    return result;
}

int playback_browser_directory_at(const u8 *browser,const u8 *node,u16 *out)
{
    fw_lock();
    u32 root = word((const u8 *)0x03076b30+13);
    int result = media_browser_directory(directory_read, 0, FS_TYPE == 3,
                                        browser,node,root,out);
    fw_unlock();return result;
}
int playback_browser_directory(const u8 *node,u16 *out)
{ return playback_browser_directory_at((const u8 *)0x03005f6c,node,out); }
