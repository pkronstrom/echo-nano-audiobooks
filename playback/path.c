#include "path.h"

static u16 le16(const u8 *p) { return p[0] | (u16)p[1] << 8; }
static u32 le32(const u8 *p) { return le16(p) | (u32)le16(p+2) << 16; }
static u16 fold(u16 c) { return c >= 'A' && c <= 'Z' ? c + 32 : c; }
static int same(const u16 *name, const u16 *wanted, u32 length)
{
    for (u32 i = 0; i < length; i++)
        if (fold(name[i]) != fold(wanted[i])) return 0;
    return !name[length] || name[length] == 0xffff;
}
static u8 checksum(const u8 *e)
{
    u8 sum = 0;
    for (u32 i = 0; i < 11; i++) sum = (sum >> 1) + ((sum & 1) << 7) + e[i];
    return sum;
}
static int short_match(const u8 *e, const u16 *wanted, u32 length)
{
    u16 name[13];
    u32 n = 0;
    for (u32 i = 0; i < 8 && e[i] != ' '; i++) name[n++] = e[i];
    if (e[8] != ' ') {
        name[n++] = '.';
        for (u32 i = 8; i < 11 && e[i] != ' '; i++) name[n++] = e[i];
    }
    name[n] = 0;
    return n == length && same(name, wanted, length);
}
static int find_fat(media_read_fn read, void *ctx, struct media_dir *parent,
                    const u16 *wanted, u32 length, struct media_ref *out)
{
    u16 name[260];
    u8 e[32], sum = 0;
    u32 expected = 0;
    int pending = 0;
    for (u32 i = 0; i < 65536; i++) {
        int r = read(ctx, 0, parent, i, e);
        if (r == 9 || (!r && !e[0])) return 0;
        if (r) return -2;
        if (e[0] == 0xe5) { pending = 0; continue; }
        if (e[11] == 15) {
            u32 seq = e[0] & 31;
            if (e[0] & 0x40) {
                pending = seq && seq <= 20;
                expected = seq; sum = e[13];
                for (u32 j = 0; j < 260; j++) name[j] = 0xffff;
            }
            if (!pending || !seq || seq > 20 || seq != expected || e[13] != sum || e[12] ||
                le16(e+26) || (e[0] & 0xa0)) { pending = 0; continue; }
            static const u8 positions[] = {1,3,5,7,9,14,16,18,20,22,24,28,30};
            for (u32 j = 0; j < 13; j++) name[(seq-1)*13+j] = le16(e+positions[j]);
            expected--;
            continue;
        }
        if (!(e[11] & 8) && e[0] != '.' &&
            ((pending && !expected && checksum(e) == sum && same(name, wanted, length)) ||
             short_match(e, wanted, length))) {
            out->parent = *parent; out->index = i;
            out->cluster = (u32)le16(e+20) << 16 | le16(e+26);
            out->size = le32(e+28); out->attrs = e[11]; out->flags = 0;
            out->filesystem = 2; out->name_units = length;
            return 1;
        }
        pending = 0;
    }
    return -2;
}
static int find_exfat(media_read_fn read, void *ctx, struct media_dir *parent,
                      const u16 *wanted, u32 length, struct media_ref *out)
{
    u8 e[32], stream[32];
    for (u32 i = 0; i < 65536; i++) {
        int r = read(ctx, 1, parent, i, e);
        if (r == 9 || (!r && !e[0])) return 0;
        if (r) return -2;
        if (e[0] != 0x85 || (e[4] & 8) || e[1] < 2) continue;
        u8 attrs = e[4], secondaries = e[1];
        if (read(ctx, 1, parent, i+1, stream)) return -2;
        if (stream[0] != 0xc0 || stream[3] != length ||
            secondaries < 1 + (length+14)/15 || le32(stream+28) ||
            le32(stream+12) || le32(stream+8) > le32(stream+24)) continue;
        int match = 1;
        for (u32 j = 0; j < length; j++) {
            if (!(j % 15) && read(ctx, 1, parent, i+2+j/15, e)) return -2;
            if (e[0] != 0xc1 || fold(le16(e+2+(j%15)*2)) != fold(wanted[j])) match = 0;
        }
        if (!match) continue;
        out->parent = *parent; out->index = i;
        out->cluster = le32(stream+20); out->size = le32(stream+24);
        out->flags = stream[1]; out->attrs = attrs;
        out->filesystem = 3; out->name_units = length;
        return 1;
    }
    return -2;
}
int media_resolve(media_read_fn read, void *ctx, int exfat,
                  const u16 *path, struct media_ref *out)
{
    if (path[0] != '/' || !path[1]) return -1;
    /* Validate before touching storage, including components after missing dirs. */
    u32 total = 0;
    while (path[total]) { if (total >= 255) return -1; total++; }
    for (u32 p = 1; p < total;) {
        u32 start = p;
        while (p < total && path[p] != '/') p++;
        u32 n = p - start;
        if (!n || (n == 1 && path[start] == '.') ||
            (n == 2 && path[start] == '.' && path[start+1] == '.')) return -1;
        p++;
    }
    if (path[total-1] == '/') return -1;
    struct media_dir parent = {0};
    for (u32 p = 1; p < total;) {
        u32 start = p;
        while (p < total && path[p] != '/') p++;
        int r = exfat ? find_exfat(read, ctx, &parent, path+start, p-start, out) :
                        find_fat(read, ctx, &parent, path+start, p-start, out);
        if (r != 1) return r;
        if (p == total) return 1;
        if (!(out->attrs & 16) || out->cluster < 2) return 0;
        parent = (struct media_dir){out->cluster, out->size, 0, out->flags};
        p++;
    }
    return 0;
}
