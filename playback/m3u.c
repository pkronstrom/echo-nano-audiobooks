#include "m3u.h"

/* Strict UTF-8: reject overlong encodings, surrogates and out-of-range scalars. */
static int scalar(const u8 *s, u32 n, u32 *used, u32 *value)
{
    u32 c = s[0], count, minimum;
    if (c < 0x80) { *used = 1; *value = c; return 1; }
    if (c >= 0xc2 && c <= 0xdf) { count = 2; minimum = 0x80; c &= 31; }
    else if (c >= 0xe0 && c <= 0xef) { count = 3; minimum = 0x800; c &= 15; }
    else if (c >= 0xf0 && c <= 0xf4) { count = 4; minimum = 0x10000; c &= 7; }
    else return 0;
    if (n < count) return 0;
    for (u32 i = 1; i < count; i++) {
        if ((s[i] & 0xc0) != 0x80) return 0;
        c = (c << 6) | (s[i] & 63);
    }
    if (c < minimum || c > 0x10ffff || (c >= 0xd800 && c <= 0xdfff)) return 0;
    *used = count; *value = c;
    return 1;
}
static int slash(u32 c) { return c == '/' || c == '\\'; }
int m3u_resolve(const u16 *base, const u8 *line, u32 len, u16 *out)
{
    if (!len || slash(line[0]) || base[0] != '/') return 0;
    u32 n = 0;
    while (base[n]) {
        if (n >= M3U_PATH_UNITS - 1) return 0;
        out[n] = base[n]; n++;
    }
    while (n > 1 && slash(out[n-1])) n--;
    for (u32 pos = 0; pos < len;) {
        while (pos < len && slash(line[pos])) pos++;
        u32 start = pos;
        while (pos < len && !slash(line[pos])) pos++;
        u32 size = pos - start;
        if (!size || (size == 1 && line[start] == '.')) continue;
        if (size == 2 && line[start] == '.' && line[start+1] == '.') {
            if (n <= 1) return 0;
            while (n > 1 && !slash(out[n-1])) n--;
            if (n > 1) n--;
            continue;
        }
        if (n > 1) {
            if (n >= M3U_PATH_UNITS - 1) return 0;
            out[n++] = '/';
        }
        while (start < pos) {
            u32 used, c;
            if (!scalar(line + start, pos - start, &used, &c)) return 0;
            if (c < 32 || c == ':' || c == '*' || c == '?' || c == '"' ||
                c == '<' || c == '>' || c == '|') return 0;
            if (c > 0xffff) {
                if (n >= M3U_PATH_UNITS - 2) return 0;
                c -= 0x10000;
                out[n++] = 0xd800 | (c >> 10);
                out[n++] = 0xdc00 | (c & 1023);
            } else {
                if (n >= M3U_PATH_UNITS - 1) return 0;
                out[n++] = c;
            }
            start += used;
        }
    }
    out[n] = 0;
    return 1;
}
/* Player service owns this parser; callbacks must not invoke m3u_scan again.
 * Keep the large scratch arrays off the stock service stack. */
u32 playback_scratch[M3U_LINE_BYTES / sizeof(u32)];
u32 playback_scratch_busy;

struct scan {
    m3u_entry_fn entry;
    void *ctx;
    const u16 *base;
    struct m3u_stats *stats;
    u32 candidates;
    u16 *path;
};
static int emit(struct scan *s, u8 *line, u32 len, u32 offset, int overflow)
{
    if (!offset && len >= 3 && line[0] == 0xef && line[1] == 0xbb && line[2] == 0xbf) {
        line += 3; len -= 3;
    }
    if (!len || line[0] == '#') return 0;
    if (s->candidates == M3U_MAX_ENTRIES) { s->stats->limited = 1; return 1; }
    s->candidates++;
    u16 *path = s->path;
    if (overflow || !m3u_resolve(s->base, line, len, path)) {
        s->stats->invalid++;
        return 0;
    }
    int result = s->entry(s->ctx, path, offset);
    if (result < 0) return -2;
    if (result) s->stats->accepted++;
    else s->stats->skipped++;
    return 0;
}
static int scan_impl(m3u_read_fn read, m3u_entry_fn entry, void *ctx, const u16 *base,
             struct m3u_stats *stats, u8 *line, u16 *path)
{
    *stats = (struct m3u_stats){0};
    struct scan s = {entry, ctx, base, stats, 0, path};
    u8 chunk[256];
    u32 offset = 0, line_offset = 0, len = 0;
    int overflow = 0, cr = 0;
    for (;;) {
        if (offset >= 1024 * 1024) { stats->limited = 1; return 0; }
        u32 requested = 1024 * 1024 - offset;
        if (requested > sizeof chunk) requested = sizeof chunk;
        int got = read(ctx, offset, chunk, requested);
        if (got < 0 || (u32)got > requested) return -1;
        if (!got) {
            int result = emit(&s, line, len, line_offset, overflow);
            return result < 0 ? result : 0;
        }
        for (int i = 0; i < got; i++, offset++) {
            u8 c = chunk[i];
            if (cr && c == '\n') { cr = 0; line_offset = offset + 1; continue; }
            cr = 0;
            if (c == '\r' || c == '\n') {
                int result = emit(&s, line, len, line_offset, overflow);
                if (result) return result < 0 ? result : 0;
                len = 0; overflow = 0; cr = c == '\r'; line_offset = offset + 1;
            } else if (len < M3U_LINE_BYTES) line[len++] = c;
            else overflow = 1;
        }
    }
}

int m3u_scan(m3u_read_fn read, m3u_entry_fn entry, void *ctx, const u16 *base,
             struct m3u_stats *stats)
{
    u16 scan_path[M3U_PATH_UNITS];
    if (playback_scratch_busy) return -3;
    playback_scratch_busy=1;
    int result=scan_impl(read,entry,ctx,base,stats,(u8 *)playback_scratch,scan_path);
    playback_scratch_busy=0;
    return result;
}

int m3u_scan_with_workspace(struct m3u_workspace *workspace, m3u_read_fn read,
                           m3u_entry_fn entry, void *ctx, const u16 *base,
                           struct m3u_stats *stats)
{
    if (workspace->busy) return -3;
    workspace->busy=1;
    int result=scan_impl(read,entry,ctx,base,stats,
                         (u8 *)workspace->line,workspace->path);
    workspace->busy=0;
    return result;
}
