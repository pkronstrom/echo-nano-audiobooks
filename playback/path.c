#include "path.h"

static u16 le16(const u8 *p) { return p[0] | (u16)p[1] << 8; }
static u32 le32(const u8 *p) { return le16(p) | (u32)le16(p+2) << 16; }
/* Share the ASCII fold helper instead of cloning it into name comparators.
 * Host fixtures also compile this file with Clang. */
#if defined(__GNUC__) && !defined(__clang__)
__attribute__((noipa))
#endif
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
static u32 short_name(const u8 *e, u16 *name)
{
    u32 n = 0;
    for (u32 i = 0; i < 8 && e[i] != ' '; i++) name[n++] = e[i];
    if (e[8] != ' ') {
        name[n++] = '.';
        for (u32 i = 8; i < 11 && e[i] != ' '; i++) name[n++] = e[i];
    }
    name[n] = 0;
    return n;
}
static int short_match(const u8 *e, const u16 *wanted, u32 length)
{
    u16 name[13];
    return short_name(e, name) == length && same(name, wanted, length);
}
struct query { const u16 *wanted; u32 length, cluster; u16 *name; u32 index; };
static int find_fat(media_read_fn read, void *ctx, struct media_dir *parent,
                    const struct query *q, struct media_ref *out)
{
    const u16 *wanted = q->wanted;
    u32 length = q->length;
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
        u32 cluster = (u32)le16(e+20) << 16 | le16(e+26);
        int long_name = pending && !expected && checksum(e) == sum;
        int match = wanted ? ((long_name && same(name, wanted, length)) ||
                               short_match(e, wanted, length)) :
                              (q->cluster ? ((e[11] & 16) && cluster == q->cluster) : i == q->index);
        if (!(e[11] & 8) && e[0] != '.' && match) {
            if (!wanted) {
                length = 0;
                if (long_name) {
                    while (length < 255 && name[length] && name[length] != 0xffff) length++;
                    if (name[length] && name[length] != 0xffff) long_name = 0;
                }
                if (!long_name) length = short_name(e, name);
                if (!length) continue;
                /* OEM short names need a codepage; do not invent a Unicode path. */
                int valid = 1;
                for (u32 j = 0; j < length; j++) {
                    if (!long_name && name[j] >= 128) valid = 0;
                    q->name[j] = name[j];
                }
                q->name[length] = 0;
                if (!valid) continue;
            }
            out->parent = *parent; out->index = i;
            out->cluster = cluster;
            out->size = le32(e+28); out->attrs = e[11]; out->flags = 0;
            out->filesystem = 2; out->name_units = length;
            return 1;
        }
        pending = 0;
    }
    return -2;
}
static int find_exfat(media_read_fn read, void *ctx, struct media_dir *parent,
                      const struct query *q, struct media_ref *out)
{
    const u16 *wanted = q->wanted;
    u32 length = q->length;
    u8 e[32], stream[32];
    for (u32 i = 0; i < 65536; i++) {
        int r = read(ctx, 1, parent, i, e);
        if (r == 9 || (!r && !e[0])) return 0;
        if (r) return -2;
        if (e[0] != 0x85 || (e[4] & 8) || e[1] < 2) continue;
        u8 attrs = e[4], secondaries = e[1];
        if (read(ctx, 1, parent, i+1, stream)) return -2;
        if (!wanted) length = stream[3];
        if (stream[0] != 0xc0 || !length || stream[3] != length ||
            secondaries < 1 + (length+14)/15 || le32(stream+28) ||
            le32(stream+12) || le32(stream+8) > le32(stream+24)) continue;
        if (!wanted && (q->cluster ? (!(attrs & 16) || le32(stream+20) != q->cluster) : i != q->index)) continue;
        int match = 1;
        for (u32 j = 0; j < length; j++) {
            if (!(j % 15) && read(ctx, 1, parent, i+2+j/15, e)) return -2;
            u16 c = le16(e+2+(j%15)*2);
            if (e[0] != 0xc1 || !c || (wanted && fold(c) != fold(wanted[j]))) match = 0;
            if (!wanted) q->name[j] = c;
        }
        if (!match) continue;
        if (!wanted) q->name[length] = 0;
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
        struct query q = {.wanted=path+start, .length=p-start};
        int r = exfat ? find_exfat(read, ctx, &parent, &q, out) :
                        find_fat(read, ctx, &parent, &q, out);
        if (r != 1) return r;
        if (p == total) return 1;
        if (!(out->attrs & 16) || out->cluster < 2) return 0;
        parent = (struct media_dir){out->cluster, out->size, 0, out->flags};
        p++;
    }
    return 0;
}

int media_directory_name(media_read_fn read, void *ctx, int exfat,
                          struct media_dir *parent, u32 child, u16 *name,
                          struct media_ref *out)
{
    name[0] = 0;
    if (child < 2 || child >= CLUSTER_BAD) return -1;
    struct query q = {.cluster=child, .name=name};
    int r = exfat ? find_exfat(read, ctx, parent, &q, out) :
                    find_fat(read, ctx, parent, &q, out);
    if (r != 1) name[0] = 0;
    return r;
}

int media_entry_name(media_read_fn read, void *ctx, int exfat,
                     struct media_dir *parent, u32 index, u16 *name,
                     struct media_ref *out)
{
    struct query q = {.index=index, .name=name};
    name[0]=0;
    return exfat ? find_exfat(read,ctx,parent,&q,out) : find_fat(read,ctx,parent,&q,out);
}
