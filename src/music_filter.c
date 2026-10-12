#include "music_filter.h"

/* Only caller-owned directory entries are modified. Never write to the card.
 * One refresh uses one filesystem; include its kind for host tests as well. */
static struct { u32 cluster; u8 fs, valid, hidden; } cache[32];
static u8 root_state[2]; /* 2 = not probed; pinned across cache collisions */
u32 music_filter_errors;
static u16 le16(const u8 *p) { return p[0] | (u16)p[1] << 8; }
static u32 le32(const u8 *p) { return le16(p) | (u32)le16(p + 2) << 16; }
static int letter(u16 c, u8 expected)
{
    if (c >= 'A' && c <= 'Z') c += 'a' - 'A';
    return c == expected;
}
static int fat_name(const u8 *e)
{
    static const u8 offsets[] = {1,3,5,7,9,14,16,18};
    const char *name = ".nomusic";
    if (e[0] != 0x41 || e[11] != 15 || e[12] || le16(e + 26)) return 0;
    for (u32 i = 0; i < 8; i++)
        if (!letter(le16(e + offsets[i]), name[i])) return 0;
    return le16(e + 20) == 0;
}
static int normal_fat(const u8 *e)
{
    return e[0] && e[0] != 0xe5 && e[0] != '.' && !(e[11] & 8);
}
void music_filter_reset(void)
{
    for (u32 i = 0; i < 32; i++) cache[i].valid = 0;
    music_filter_errors = 0;
    root_state[0] = root_state[1] = 2;
}
/* desc is a mutable copy: the stock exFAT reader normalizes root descriptors. */
static int marked(u32 cluster, u32 *desc)
{
    u32 fs = desc != 0, slot = (cluster ^ fs) % 32;
    if (cache[slot].valid && cache[slot].cluster == cluster && cache[slot].fs == fs)
        return cache[slot].hidden;
    u8 e[32], checksum = 0;
    int pending = 0, hidden = 0;
    u32 i;
    for (i = 0; i < 65536; i++) {
        if (!(i & 63)) music_watchdog();
        int r = desc ? music_exfat_original(e, desc, i) : music_fat_original(e, cluster, i);
        if (r == 9 || (!r && !e[0])) break;
        if (r) { hidden = 1; music_filter_errors++; break; }
        if (!desc) {
            if (pending && normal_fat(e) && !(e[11] & 16)) {
                u8 sum = 0;
                for (u32 j = 0; j < 11; j++) sum = (sum >> 1) + ((sum & 1) << 7) + e[j];
                if (sum == checksum) { hidden = 1; break; }
            }
            pending = fat_name(e);
            checksum = e[13];
        } else {
            if (pending == 2 && e[0] == 0xc1) {
                const char *name = ".nomusic";
                u32 j;
                for (j = 0; j < 8 && letter(le16(e + 2 + 2*j), name[j]); j++) {}
                if (j == 8) { hidden = 1; break; }
            }
            if (pending == 1 && e[0] == 0xc0 && e[3] == 8) pending = 2;
            else pending = e[0] == 0x85 && e[1] >= 2 && !(e[4] & 16);
        }
    }
    if (i == 65536) { hidden = 1; music_filter_errors++; }
    cache[slot].cluster = cluster;
    cache[slot].fs = fs;
    cache[slot].hidden = hidden;
    cache[slot].valid = 1;
    return hidden;
}
static int root_marked(int exfat)
{
    if (root_state[exfat] == 2) {
        u32 root[4] = {0};
        root_state[exfat] = marked(0, exfat ? root : 0);
    }
    return root_state[exfat];
}
int music_fat_entry(u8 *out, u32 cluster, u32 index)
{
    int r = music_fat_original(out, cluster, index);
    if (!r && normal_fat(out) && (root_marked(0) || marked(cluster, 0) ||
        ((out[11] & 16) && marked((u32)le16(out + 20) << 16 | le16(out + 26), 0))))
        out[11] |= 2;
    return r;
}
int music_exfat_entry(u8 *out, const void *desc, u32 index)
{
    int r = music_exfat_original(out, desc, index);
    if (r || out[0] != 0x85) return r;
    u32 local[4];
    __builtin_memcpy(local, desc, sizeof local);
    int hide = root_marked(1) || marked(local[0], local);
    if (!hide && (out[4] & 16)) {
        u8 stream[32];
        r = music_exfat_original(stream, local, index + 1);
        if (r || stream[0] != 0xc0 || le32(stream + 28)) {
            hide = 1;
            music_filter_errors++;
        } else {
            local[0] = le32(stream + 20);
            local[1] = le32(stream + 24);
            local[2] = 0;
            local[3] = stream[1];
            hide = marked(local[0], local);
        }
    }
    if (hide) out[4] |= 2;
    return 0;
}
